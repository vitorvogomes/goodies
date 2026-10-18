"""Métricas de sucesso da v2 num comando (Story 10.5 — NFR-12, PRD §7).

Lê só `categorization_events`, `alert_dismissals`, `month_closes` e as tabelas de fato — não grava
nada, salvo o registro da SM-1 (`metric_events`):

    uv run python -m scripts.ops.metricas --de 2026-11 --ate 2026-12
    uv run python -m scripts.ops.metricas --sm1-inicio 2026-10-18 [--escopo caixa|v2]
    uv run python -m scripts.ops.metricas --planilha-aberta "conferir o saldo" [--escopo caixa|v2]

- SM-2: meses fechados com o saldo PF conferido.
- SM-3: meses fechados com o patrimônio por classe dentro da tolerância (consolidado B3 do fim do
  mês, AD-13); sem consolidado daquele fim de mês → "sem origem". As carteiras não têm origem por
  fim de mês (o scan é o de agora): entram como a conferência de hoje (conferidas × total).
- SM-4: preços digitados no período para ativos que têm fonte de mercado (os sem fonte não contam).
- SM-5: % das transações novas (do import) categorizadas por regra, por semana; o denominador são
  todas as novas, inclusive as que ficaram "a classificar" (sem evento).
- SM-6: correções por semana (só `cause ∈ {review, inline_edit}` que mudam a categoria; confirmar
  sem mudar não é correção).
- SM-C1: % das categorizações automáticas (regra/sugestão no import) corrigidas depois de
  confirmadas: a primeira revisão/edição confirma; só uma mudança posterior conta.
- Os limites do período e as semanas são no horário de Brasília.
- SM-C2: avisos dispensados sem ação.
- SM-1: dias seguidos sem abrir a planilha "Rotina", por escopo (`caixa` = a parcial do marco 2;
  abrir para a caixa zera os dois; abrir para o resto da v2 zera só o `v2`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from config import settings
from engines.common.dates import add_months, month_end, parse_periodo, today_brt
from engines.common.owner import get_owner_id

SM1_GOAL_DAYS = 30
_CORRECTION_CAUSES = ("review", "inline_edit")
_AUTO_SOURCES = ("rule", "suggestion")
_IMPORT_SOURCES = ("nubank_ofx", "nubank_csv")  # transação "nova" = a que chegou por arquivo
_BRT = ZoneInfo("America/Sao_Paulo")


@dataclass
class Report:
    de: date
    ate: date
    sm2_closed: int = 0
    sm2_checked: int = 0
    sm3_closed: int = 0
    sm3_within: int = 0
    sm3_no_origin: int = 0
    sm3_wallets_ok: int = 0
    sm3_wallets_total: int = 0
    sm3_wallets_stale: bool = False
    sm4_typed: int = 0
    sm5_by_week: dict[str, tuple[int, int]] = field(default_factory=dict)  # semana → (regra, total)
    sm5_rule_pct: float | None = None
    sm6_corrections_by_week: dict[str, int] = field(default_factory=dict)
    sm_c1_auto: int = 0
    sm_c1_corrected: int = 0
    sm_c1_pct: float | None = None
    sm_c2_dismissed: int = 0
    sm_c2_by_key: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Streak:
    scope: str
    start: date
    last_opening: date | None
    days: int

    @property
    def met(self) -> bool:
        return self.days >= SM1_GOAL_DAYS


def _week(when: datetime) -> str:
    year, week, _ = when.astimezone(_BRT).isocalendar()
    return f"{year}-S{week:02d}"


async def compute(conn: asyncpg.Connection, de: date, ate: date) -> Report:
    """Todas as métricas do período (meses `de` … `ate`, inclusive). Só lê."""
    from engines.market import service as market_service
    from engines.portfolio import reconciliation

    r = Report(de=de, ate=ate)
    start = datetime.combine(de, time.min, tzinfo=_BRT)
    end = datetime.combine(add_months(ate, 1), time.min, tzinfo=_BRT)

    # SM-2 e SM-3: os meses fechados do período (a versão vigente)
    closes = await conn.fetch(
        "SELECT DISTINCT ON (month) month, version, status FROM month_closes "
        "WHERE month BETWEEN $1 AND $2 ORDER BY month, version DESC",
        de,
        ate,
    )
    owner = await get_owner_id(conn)
    for c in closes:
        if c["status"] != "closed":
            continue
        r.sm2_closed += 1
        r.sm3_closed += 1
        checked = await conn.fetchval(
            "SELECT saldo_conferido FROM month_summary_totals WHERE month = $1 AND version = $2",
            c["month"],
            c["version"],
        )
        r.sm2_checked += 1 if checked else 0
        ref = month_end(c["month"])
        has_origin = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM broker_position_snapshots WHERE ref_date = $1)", ref
        )
        if not has_origin:
            r.sm3_no_origin += 1
            continue
        b3 = await reconciliation.b3_reconciliation(conn, owner, ref)
        r.sm3_within += 0 if any(x.status == "divergente" for x in b3.rows) else 1
    wallets = await reconciliation.wallet_reconciliation(conn, owner)
    r.sm3_wallets_total = len(wallets.rows)
    r.sm3_wallets_ok = sum(1 for x in wallets.rows if x.status != "divergente")
    r.sm3_wallets_stale = wallets.stale

    # SM-4: preços digitados no período para ativos que têm fonte de mercado
    typed = await conn.fetch(
        "SELECT DISTINCT ticker, ref_date FROM asset_price_history WHERE is_manual "
        "AND ref_date BETWEEN $1 AND $2",
        de,
        month_end(ate),
    )
    for row in typed:
        if await market_service.has_market_source(conn, row["ticker"]):
            r.sm4_typed += 1

    # SM-5: as transações novas do período (por arquivo, pelo Hub — o lote `legacy` é a base de
    # antes da v2) e quantas chegaram por regra no import
    weeks: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for t in await conn.fetch(
        "SELECT t.created_at, EXISTS (SELECT 1 FROM categorization_events e "
        "WHERE e.transaction_id = t.id AND e.cause = 'import' AND e.source = 'rule') AS by_rule "
        "FROM transactions t JOIN import_batches b ON b.id = t.batch_id AND b.status <> 'legacy' "
        "WHERE t.source = ANY($1::text[]) AND t.created_at >= $2 AND t.created_at < $3",
        list(_IMPORT_SOURCES),
        start,
        end,
    ):
        week = weeks[_week(t["created_at"])]
        week[1] += 1
        week[0] += 1 if t["by_rule"] else 0
    r.sm5_by_week = {k: (v[0], v[1]) for k, v in sorted(weeks.items())}
    rule = sum(v[0] for v in weeks.values())
    total = sum(v[1] for v in weeks.values())
    r.sm5_rule_pct = rule / total * 100 if total else None

    # SM-6 e SM-C1: os eventos de categorização do período
    events = await conn.fetch(
        "SELECT transaction_id, source, cause, before_category_id, after_category_id, created_at "
        "FROM categorization_events WHERE created_at >= $1 AND created_at < $2 "
        "ORDER BY created_at",
        start,
        end,
    )
    auto: set[str] = set()
    confirmed: dict[str, Any] = {}  # transação automática → categoria na confirmação
    corrected: set[str] = set()
    for e in events:
        tx = str(e["transaction_id"])
        if e["cause"] == "import":
            if e["source"] in _AUTO_SOURCES:
                auto.add(tx)
            continue
        if e["cause"] not in _CORRECTION_CAUSES:
            continue
        if e["before_category_id"] != e["after_category_id"]:
            label = _week(e["created_at"])
            r.sm6_corrections_by_week[label] = r.sm6_corrections_by_week.get(label, 0) + 1
        if tx not in auto:
            continue
        if tx not in confirmed:
            confirmed[tx] = e["after_category_id"]  # a primeira revisão/edição confirma
        elif e["after_category_id"] != confirmed[tx]:
            corrected.add(tx)
    r.sm_c1_auto, r.sm_c1_corrected = len(auto), len(corrected)
    r.sm_c1_pct = len(corrected) / len(auto) * 100 if auto else None

    # SM-C2: avisos dispensados no período
    for d in await conn.fetch(
        "SELECT key FROM alert_dismissals WHERE dismissed_at >= $1 AND dismissed_at < $2",
        start,
        end,
    ):
        kind = d["key"].split(":", 1)[0]
        r.sm_c2_by_key[kind] = r.sm_c2_by_key.get(kind, 0) + 1
        r.sm_c2_dismissed += 1
    return r


async def record(
    conn: asyncpg.Connection,
    kind: str,
    day: date,
    *,
    scope: str = "v2",
    note: str | None = None,
) -> None:
    """Grava o início da SM-1 ou uma abertura da planilha (o único que o comando escreve)."""
    await conn.execute(
        "INSERT INTO metric_events (kind, scope, day, note) VALUES ($1, $2, $3, $4)",
        kind,
        scope,
        day,
        note,
    )


async def sm1(conn: asyncpg.Connection, *, today: date | None = None) -> list[Streak]:
    """Dias seguidos sem abrir a planilha desde o início (ou desde a última abertura), por escopo.
    Abrir para a caixa zera os dois escopos; abrir para o resto da v2 zera só o `v2`."""
    today = today or today_brt()
    rows = await conn.fetch("SELECT kind, scope, day FROM metric_events ORDER BY day")
    starts = {r["scope"]: r["day"] for r in rows if r["kind"] == "sm1_inicio"}
    out: list[Streak] = []
    for scope, start in sorted(starts.items()):
        hits = ("caixa",) if scope == "caixa" else ("caixa", "v2")
        openings = [
            r["day"]
            for r in rows
            if r["kind"] == "planilha_aberta" and r["scope"] in hits and r["day"] >= start
        ]
        last = max(openings) if openings else None
        out.append(Streak(scope, start, last, (today - (last or start)).days))
    return out


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%".replace(".", ",")


def render(r: Report, streaks: list[Streak]) -> str:
    lines = [f"Métricas de {r.de:%m/%Y} a {r.ate:%m/%Y}", ""]
    lines.append("SM-1 — dias seguidos sem abrir a planilha (meta ≥ 30):")
    if not streaks:
        lines.append("  não iniciada (use --sm1-inicio <data>)")
    for s in streaks:
        last = f", última abertura {s.last_opening:%d/%m/%Y}" if s.last_opening else ""
        status = "na meta" if s.met else "abaixo da meta"
        name = "caixa (parcial do marco 2)" if s.scope == "caixa" else "v2"
        lines.append(f"  {name}: {s.days} dias desde {s.start:%d/%m/%Y}{last} — {status}")
    lines += [
        f"SM-2 — meses fechados com o saldo PF conferido: {r.sm2_checked} de {r.sm2_closed}",
        f"SM-3 — meses fechados com o patrimônio dentro da tolerância: {r.sm3_within} de "
        f"{r.sm3_closed - r.sm3_no_origin} com origem ({r.sm3_no_origin} sem consolidado B3)",
        f"  carteiras hoje: {r.sm3_wallets_ok} de {r.sm3_wallets_total} conferidas"
        + (" (scan desatualizado)" if r.sm3_wallets_stale else ""),
        f"SM-4 — preços digitados para ativos com fonte de mercado: {r.sm4_typed}",
        f"SM-5 — transações novas por regra: {_pct(r.sm5_rule_pct)} (meta ≥ 80%)",
    ]
    for week, (rule, total) in r.sm5_by_week.items():
        lines.append(f"  {week}: {rule} de {total}")
    lines.append("SM-6 — correções na revisão por semana:")
    for week, n in sorted(r.sm6_corrections_by_week.items()):
        lines.append(f"  {week}: {n}")
    if not r.sm6_corrections_by_week:
        lines.append("  nenhuma")
    lines += [
        f"SM-C1 — automáticas corrigidas depois: {_pct(r.sm_c1_pct)} "
        f"({r.sm_c1_corrected} de {r.sm_c1_auto})",
        f"SM-C2 — avisos dispensados sem ação: {r.sm_c2_dismissed}"
        + (f" ({json.dumps(r.sm_c2_by_key, ensure_ascii=False)})" if r.sm_c2_by_key else ""),
    ]
    return "\n".join(lines)


async def _main(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        if args.sm1_inicio:
            await record(conn, "sm1_inicio", date.fromisoformat(args.sm1_inicio), scope=args.escopo)
            print(f"SM-1 ({args.escopo}) começa em {date.fromisoformat(args.sm1_inicio):%d/%m/%Y}.")
            return
        if args.planilha_aberta:
            await record(
                conn, "planilha_aberta", today_brt(), scope=args.escopo, note=args.planilha_aberta
            )
            print(f"Abertura da planilha registrada ({args.escopo}): {args.planilha_aberta}")
            return
        ate = parse_periodo(args.ate) if args.ate else today_brt().replace(day=1)
        de = parse_periodo(args.de) if args.de else add_months(ate, -2)
        print(render(await compute(conn, de, ate), await sm1(conn)))
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--de", help="AAAA-MM (padrão: dois meses antes de --ate)")
    parser.add_argument("--ate", help="AAAA-MM (padrão: o mês atual)")
    parser.add_argument("--sm1-inicio", help="AAAA-MM-DD: grava o início da contagem da SM-1")
    parser.add_argument(
        "--planilha-aberta", help='"motivo": registra uma abertura da planilha hoje'
    )
    parser.add_argument("--escopo", choices=("caixa", "v2"), default="v2")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
