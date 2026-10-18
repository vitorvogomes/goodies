"""Engine `closing` (camada 5 — AD-8): a única forma de calcular o resumo de um mês.

`build_month_summary(conn, month, as_of)` chama os construtores por mês de `ledger` e `portfolio`
(termos da AD-7) com `as_of` = fim do mês, ou hoje no mês corrente. `month_summary` é a leitura das
telas: mês aberto, ao vivo; mês fechado, a versão vigente do snapshot, nunca recalculada (5.5).
"""

from __future__ import annotations

import calendar
import json
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg

from engines.common.alerts import brl
from engines.common.dates import MIN_MONTH, today_brt
from engines.common.month_status import MonthState as PortState
from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.portfolio import calc as portfolio_calc
from engines.portfolio.valuation import valuation_as_of

from .checks import label, run_checks
from .models import (
    Checklist,
    ChecklistItem,
    CloseCheck,
    CloseOut,
    MonthState,
    MonthSummary,
    Recovery,
    RecoveryMonth,
    RecoveryStep,
    ReopenOut,
    ReopenPreview,
    ReopenRow,
)


def month_end(month: date) -> date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def default_as_of(month: date) -> date:
    today = today_brt()
    return min(month_end(month), today)


async def build_month_summary(
    conn: asyncpg.Connection, month: date, as_of: date | None = None
) -> MonthSummary:
    as_of = as_of or default_as_of(month)
    ledger = await ledger_service.ledger_month(conn, month)
    owner = await get_owner_id(conn)
    valuation = await valuation_as_of(conn, owner, as_of)
    accounts = await ledger_service.accounts_balance(conn, as_of)
    invested = valuation.invested
    # Receita do trabalho vem do MEI: se ele não cobre o mês, trabalho e poupança ficam defasados.
    mei = next(
        (
            s
            for s in await ingest_service.sources(conn, today_brt(), with_balances=False)
            if s.key == "nubank_mei"
        ),
        None,
    )
    mei_until = mei.updated_until if mei is not None else None
    income_stale = mei_until is not None and mei_until < month_end(month) and as_of >= mei_until
    rate = ledger.taxa_poupanca
    return MonthSummary(
        month=month,
        as_of=as_of,
        receitas=ledger.receitas,
        trabalho=ledger.trabalho,
        resgates=ledger.resgates,
        devolucoes=ledger.devolucoes,
        gastos=ledger.gastos,
        investido=ledger.investido,
        taxa_poupanca=rate * 100 if rate is not None else None,
        resultado_mes=ledger.resultado,
        receitas_por_pagador=ledger.receitas_por_pagador,
        gastos_por_categoria=ledger.gastos_por_categoria,
        ledger_as_of=ledger.data_as_of,
        income_as_of=mei_until if income_stale else ledger.data_as_of,
        income_stale=income_stale,
        saldo_conferido_pf=await ledger_service.pf_month_checked(conn, month_end(month)),
        saldo_contas=accounts.value,
        valor_investido=invested,
        patrimonio=portfolio_calc.patrimony(invested, accounts=accounts.value),
        aplicado=valuation.contributed,
        resultado_investimentos=valuation.result,
        rentabilidade=(Decimal(repr(valuation.xirr)) * 100 if valuation.xirr is not None else None),
        valor_por_classe=valuation.by_class,
        valor_por_ativo=valuation.by_asset,
        asset_ids_value=valuation.by_asset_id,
        flows=valuation.flows,
        caixa_corretora=valuation.broker_cash,
        portfolio_as_of=valuation.data_as_of,
        portfolio_stale=valuation.stale,
        coverage=valuation.coverage,
    )


# --------------------------------------------------------------------------------------------
# Fechar o mês: precondições, snapshot e versões (Story 5.3 — FR-32)
# --------------------------------------------------------------------------------------------

# Termos da AD-7 sem engine ainda: congelados nulos com o motivo (AD-8).
_FUTURE_TERMS = (
    "consumido",
    "a_caminho",
    "disponivel",
    "restante",
    "restante_sem_resgates",
    "consumo_financiado",
    "realizado",
    "pendente",
)


class CloseError(Exception):
    def __init__(self, code: str, message: str, checks: list[CloseCheck] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.checks = checks or []


async def latest_close(conn: asyncpg.Connection, month: date) -> asyncpg.Record | None:
    row: asyncpg.Record | None = await conn.fetchrow(
        "SELECT * FROM month_closes WHERE month = $1 ORDER BY version DESC LIMIT 1", month
    )
    return row


async def close_month(
    conn: asyncpg.Connection,
    month: date,
    confirmed: list[str],
    *,
    origin: str = "live",
) -> CloseOut:
    """Fecha o mês: recusa com bloqueio; pede "fechar mesmo assim" das `confirma` (fica gravado);
    grava a versão seguinte com o resumo de `build_month_summary` (as_of = fim do mês)."""
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('close:' || $1))", str(month))
        last = await latest_close(conn, month)
        if last is not None and last["status"] == "closed":
            raise CloseError("mes_fechado", f"{label(month)} já está fechado.")
        checks = await run_checks(conn, month)
        blocking = [c for c in checks if c.kind == "bloqueia"]
        if blocking:
            raise CloseError("fechamento_bloqueado", blocking[0].message, blocking)
        missing = [c for c in checks if c.kind == "confirma" and c.code not in confirmed]
        if missing:
            raise CloseError(
                "confirmacao_pendente", "Confirme as pendências para fechar mesmo assim.", missing
            )
        accepted = [c for c in checks if c.kind == "confirma"]
        summary = await build_month_summary(conn, month, month_end(month))
        version = (last["version"] if last is not None else 0) + 1
        await _store(conn, summary, version, accepted, origin)
    return CloseOut(month=month, version=version, confirmations=accepted)


# Colunas de `month_summary_totals` que o resumo de hoje preenche (as de `_FUTURE_TERMS` não).
_MONEY = (
    "receitas",
    "trabalho",
    "resgates",
    "devolucoes",
    "gastos",
    "investido",
    "resultado_mes",
    "saldo_contas",
    "caixa_corretora",
    "valor_investido",
    "patrimonio",
    "aplicado",
    "resultado_investimentos",
)
_PCT = ("taxa_poupanca", "rentabilidade")
_TERMS = (*_MONEY, *_PCT)
_LABELS = {
    "receitas": "Receitas",
    "trabalho": "Receita do trabalho",
    "resgates": "Resgates",
    "devolucoes": "Devoluções",
    "gastos": "Gastos",
    "investido": "Investido no mês",
    "resultado_mes": "Resultado do mês",
    "saldo_contas": "Saldo em conta",
    "caixa_corretora": "Caixa na corretora",
    "valor_investido": "Valor investido",
    "patrimonio": "Patrimônio",
    "aplicado": "Aplicado",
    "resultado_investimentos": "Resultado dos investimentos",
    "taxa_poupanca": "Taxa de poupança (%)",
    "rentabilidade": "Rentabilidade (% a.a.)",
}
_CENT = Decimal("0.01")

Line = tuple[str, str, str, date | None, Decimal]


def _totals(s: MonthSummary) -> tuple[dict[str, Any], dict[str, str]]:
    totals: dict[str, Any] = {t: getattr(s, t) for t in _MONEY}
    totals["taxa_poupanca"] = s.taxa_poupanca
    totals["rentabilidade"] = s.rentabilidade
    totals["saldo_conferido"] = s.saldo_conferido_pf
    unavailable = {t: "fora_do_resumo" for t in _FUTURE_TERMS}
    if s.taxa_poupanca is None:
        unavailable["taxa_poupanca"] = "sem_receita"
    if s.rentabilidade is None:
        unavailable["rentabilidade"] = "sem_preco"
    return totals, unavailable


def _lines(s: MonthSummary) -> list[Line]:
    lines: list[Line] = []
    lines += [("receitas", "payer", k, None, v) for k, v in s.receitas_por_pagador.items()]
    lines += [("gastos", "category", k, None, v) for k, v in s.gastos_por_categoria.items()]
    lines += [("valor", "class", k, None, v) for k, v in s.valor_por_classe.items()]
    lines += [("valor", "asset", k, None, v) for k, v in s.asset_ids_value.items()]
    lines += [("fluxo", "class", k, d, v) for (k, d), v in s.flows.items()]
    return lines


async def _store(
    conn: asyncpg.Connection,
    s: MonthSummary,
    version: int,
    accepted: list[CloseCheck],
    origin: str,
) -> None:
    totals, unavailable = _totals(s)
    await _write_version(
        conn,
        s.month,
        version,
        as_of=s.as_of,
        totals=totals,
        unavailable=unavailable,
        lines=_lines(s),
        coverage=s.coverage,
        confirmations=[c.model_dump(mode="json") for c in accepted],
        origin=origin,
    )


async def _write_version(
    conn: asyncpg.Connection,
    month: date,
    version: int,
    *,
    as_of: date,
    totals: dict[str, Any],
    unavailable: dict[str, str],
    lines: list[Line],
    coverage: dict[str, str],
    confirmations: list[dict[str, Any]],
    origin: str,
    dirty: bool = False,
) -> None:
    await conn.execute(
        "INSERT INTO month_closes (month, version, status, coverage, confirmations, origin, dirty) "
        "VALUES ($1, $2, 'closed', $3::jsonb, $4::jsonb, $5, $6)",
        month,
        version,
        json.dumps(coverage),
        json.dumps(confirmations),
        origin,
        dirty,
    )
    columns = [*_TERMS, "saldo_conferido"]
    await conn.execute(
        f"INSERT INTO month_summary_totals (month, version, as_of, {', '.join(columns)}, "
        f"unavailable) VALUES ($1, $2, $3, "
        + ", ".join(f"${i}" for i in range(4, 4 + len(columns)))
        + f", ${4 + len(columns)}::jsonb)",
        month,
        version,
        as_of,
        *[totals.get(c) for c in columns],
        json.dumps(unavailable),
    )
    await conn.executemany(
        "INSERT INTO month_summary_lines "
        "(month, version, metric, dimension_kind, dimension_id, flow_date, value) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
        [(month, version, m, kind, dim, d, v) for m, kind, dim, d, v in lines],
    )


# --------------------------------------------------------------------------------------------
# Fechamento retroativo (Story 5.7 — FR-7)
# --------------------------------------------------------------------------------------------

# Termos de planejamento que não existiam nos meses retroativos (não é "fora do resumo").
_RETRO_UNDEFINED = ("pendente", "aporte_planejado")


async def close_retro(conn: asyncpg.Connection, month: date) -> CloseOut | None:
    """Fecha um mês passado com origin `retro`, pelo mesmo resumo (`build_month_summary`).

    Mês com qualquer versão fica como está (idempotente). As pendências `confirma` são aceitas
    com o motivo "retroativo"; o saldo PF divergente vira `confirma` com "retroativo divergente ·
    R$ x". Os outros bloqueios (pendentes, mês em curso) continuam bloqueando. Sem consolidado B3
    daquele fim de mês, a cobertura da B3 é "patrimônio não coberto".
    """
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('close:' || $1))", str(month))
        if await latest_close(conn, month) is not None:
            return None
        accepted: list[CloseCheck] = []
        for c in await run_checks(conn, month):
            if c.code == "saldo_pf_divergente":
                reason = "retroativo divergente" + (
                    f" · {brl(c.amount)}" if c.amount is not None else ""
                )
                accepted.append(c.model_copy(update={"kind": "confirma", "reason": reason}))
            elif c.kind == "bloqueia":
                raise CloseError("fechamento_bloqueado", c.message, [c])
            else:
                accepted.append(c.model_copy(update={"reason": "retroativo"}))
        summary = await build_month_summary(conn, month, month_end(month))
        totals, unavailable = _totals(summary)
        unavailable.update({t: "nao_definido" for t in _RETRO_UNDEFINED})
        coverage = dict(summary.coverage)
        if any(c.code == "consolidado_ausente" for c in accepted):
            coverage["B3"] = "patrimônio não coberto"
        await _write_version(
            conn,
            month,
            1,
            as_of=summary.as_of,
            totals=totals,
            unavailable=unavailable,
            lines=_lines(summary),
            coverage=coverage,
            confirmations=[c.model_dump(mode="json") for c in accepted],
            origin="retro",
        )
    return CloseOut(month=month, version=1, confirmations=accepted)


# --------------------------------------------------------------------------------------------
# Ler o snapshot, reabrir e fechar de novo (Story 5.5 — FR-33)
# --------------------------------------------------------------------------------------------


async def _frozen(
    conn: asyncpg.Connection, month: date, version: int
) -> tuple[asyncpg.Record, list[asyncpg.Record]]:
    totals = await conn.fetchrow(
        "SELECT * FROM month_summary_totals WHERE month = $1 AND version = $2", month, version
    )
    lines = await conn.fetch(
        "SELECT metric, dimension_kind, dimension_id, flow_date, value FROM month_summary_lines "
        "WHERE month = $1 AND version = $2",
        month,
        version,
    )
    return totals, lines


async def _snapshot_summary(conn: asyncpg.Connection, close: asyncpg.Record) -> MonthSummary:
    """O snapshot vigente como `MonthSummary` (`source="snapshot"`): só os campos congelados; o
    termo nulo sai 0 com o motivo em `unavailable` (a tela mostra "—")."""
    month, version = close["month"], close["version"]
    t, lines = await _frozen(conn, month, version)
    unavailable: dict[str, str] = dict(json.loads(t["unavailable"]))
    money: dict[str, Decimal] = {}
    for term in _MONEY:
        if t[term] is None:
            unavailable.setdefault(term, "fora_do_resumo")
        money[term] = t[term] if t[term] is not None else Decimal("0")
    by: dict[tuple[str, str], dict[str, Decimal]] = {}
    flows: dict[tuple[str, date], Decimal] = {}
    for line in lines:
        if line["metric"] == "fluxo":
            flows[(line["dimension_id"], line["flow_date"])] = line["value"]
        else:
            key = (line["metric"], line["dimension_kind"])
            by.setdefault(key, {})[line["dimension_id"]] = line["value"]
    by_asset_id = by.get(("valor", "asset"), {})
    tickers = {
        str(r["id"]): r["key"]
        for r in await conn.fetch(
            "SELECT id, key FROM assets WHERE id = ANY($1::uuid[])", list(by_asset_id)
        )
    }
    as_of = t["as_of"]
    return MonthSummary(
        month=month,
        as_of=as_of,
        source="snapshot",
        **money,
        taxa_poupanca=t["taxa_poupanca"],
        rentabilidade=t["rentabilidade"],
        receitas_por_pagador=by.get(("receitas", "payer"), {}),
        gastos_por_categoria=by.get(("gastos", "category"), {}),
        ledger_as_of=as_of,
        income_as_of=as_of,
        income_stale=False,
        saldo_conferido_pf=t["saldo_conferido"],
        valor_por_classe=by.get(("valor", "class"), {}),
        valor_por_ativo={tickers.get(k, k): v for k, v in by_asset_id.items()},
        asset_ids_value=by_asset_id,
        flows=flows,
        portfolio_as_of=as_of,
        portfolio_stale=False,
        coverage=dict(json.loads(close["coverage"])),
        unavailable=unavailable,
    )


async def month_summary(conn: asyncpg.Connection, month: date) -> MonthSummary:
    """Leitura das telas (AD-8): mês fechado → versão vigente do snapshot; aberto → ao vivo."""
    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        return await _snapshot_summary(conn, close)
    return await build_month_summary(conn, month)


def _cents(v: Decimal | None) -> Decimal | None:
    return v.quantize(_CENT) if v is not None else None


async def _closed(conn: asyncpg.Connection, month: date) -> asyncpg.Record:
    close = await latest_close(conn, month)
    if close is None or close["status"] != "closed":
        raise CloseError("mes_aberto", f"{label(month)} não está fechado.")
    return close


async def reopen_preview(conn: asyncpg.Connection, month: date) -> ReopenPreview:
    """Congelado × recalculado só nas métricas que mudam, com o mesmo arredondamento (2 casas)."""
    close = await _closed(conn, month)
    frozen, _ = await _frozen(conn, month, close["version"])
    live = await build_month_summary(conn, month, month_end(month))
    rows = []
    for term in _TERMS:
        before, after = _cents(frozen[term]), _cents(getattr(live, term))
        if before != after:
            rows.append(ReopenRow(metric=term, label=_LABELS[term], frozen=before, live=after))
    return ReopenPreview(month=month, version=close["version"], rows=rows)


async def reopen_month(conn: asyncpg.Connection, month: date) -> ReopenOut:
    """Reabre a versão vigente; fechar de novo cria a `version + 1` (nada é apagado)."""
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('close:' || $1))", str(month))
        close = await _closed(conn, month)
        await conn.execute(
            "UPDATE month_closes SET status = 'reopened', reopened_at = now() "
            "WHERE month = $1 AND version = $2",
            month,
            close["version"],
        )
    return ReopenOut(month=month, version=close["version"], status="reopened")


async def refechar(conn: asyncpg.Connection, month: date, *, mode: str = "completar") -> CloseOut:
    """Grava a `version + 1` de um mês fechado, com o mesmo `origin` (Story 5.5).

    `completar`: copia o congelado e preenche só as colunas nulas ou `fora_do_resumo` com o resumo
    de agora (o caminho para um termo novo chegar aos meses fechados); `recalcular`: tudo de novo.
    """
    if mode not in ("completar", "recalcular"):
        raise ValueError(mode)
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('close:' || $1))", str(month))
        close = await _closed(conn, month)
        version = close["version"]
        live = await build_month_summary(conn, month, month_end(month))
        live_totals, live_unavailable = _totals(live)
        confirmations = list(json.loads(close["confirmations"]))
        if mode == "recalcular":
            totals, unavailable, lines = live_totals, live_unavailable, _lines(live)
            coverage, dirty = live.coverage, False
        else:
            frozen, frozen_lines = await _frozen(conn, month, version)
            was = dict(json.loads(frozen["unavailable"]))
            missing = {
                c
                for c in (*_TERMS, "saldo_conferido")
                if frozen[c] is None or was.get(c) == "fora_do_resumo"
            }
            totals = {
                c: live_totals[c] if c in missing else frozen[c]
                for c in (*_TERMS, "saldo_conferido")
            }
            unavailable = {
                t: r for t, r in live_unavailable.items() if t in _FUTURE_TERMS or t in missing
            }
            lines = [
                (r["metric"], r["dimension_kind"], r["dimension_id"], r["flow_date"], r["value"])
                for r in frozen_lines
            ]
            have = {(m, kind) for m, kind, *_ in lines}
            lines += [ln for ln in _lines(live) if (ln[0], ln[1]) not in have]
            coverage = {**live.coverage, **dict(json.loads(close["coverage"]))}
            dirty = close["dirty"]
        await conn.execute(
            "UPDATE month_closes SET status = 'reopened', reopened_at = now() "
            "WHERE month = $1 AND version = $2",
            month,
            version,
        )
        await _write_version(
            conn,
            month,
            version + 1,
            as_of=month_end(month),
            totals=totals,
            unavailable=unavailable,
            lines=lines,
            coverage=coverage,
            confirmations=confirmations,
            origin=close["origin"],
            dirty=dirty,
        )
    accepted = [CloseCheck(**c) for c in confirmations]
    return CloseOut(month=month, version=version + 1, confirmations=accepted)


class ClosingMonthStatus:
    """`MonthStatusPort` real (AD-8): fechado pela versão vigente; ajuste = fechado e tocado
    depois (`dirty`, Story 5.6)."""

    async def status(self, conn: Any, month: date) -> PortState:
        row = await latest_close(conn, month)
        if row is None or row["status"] != "closed":
            return "aberto"
        return "ajuste" if row["dirty"] else "fechado"

    async def is_closed(self, conn: Any, month: date) -> bool:
        row = await latest_close(conn, month)
        return row is not None and row["status"] == "closed"

    async def mark_dirty(self, conn: Any, month: date) -> None:
        await conn.execute(
            "UPDATE month_closes SET dirty = true, dirty_count = dirty_count + 1 "
            "WHERE month = $1 AND status = 'closed' "
            "AND version = (SELECT max(version) FROM month_closes WHERE month = $1)",
            month,
        )


# --------------------------------------------------------------------------------------------
# Estado dos meses e checklist do fechamento (Story 5.4)
# --------------------------------------------------------------------------------------------


async def month_states(conn: asyncpg.Connection, start: date, end: date) -> list[MonthState]:
    rows = {
        r["month"]: r
        for r in await conn.fetch(
            "SELECT DISTINCT ON (month) month, version, status, closed_at, origin, dirty "
            "FROM month_closes WHERE month BETWEEN $1 AND $2 ORDER BY month, version DESC",
            start,
            end,
        )
    }
    out: list[MonthState] = []
    month = start
    while month <= end:
        r = rows.get(month)
        closed = r is not None and r["status"] == "closed"
        out.append(
            MonthState(
                month=month,
                status=("ajuste" if r["dirty"] else "fechado") if closed and r else "aberto",
                version=r["version"] if r is not None else None,
                closed_at=r["closed_at"] if closed and r else None,
                origin=r["origin"] if r is not None else None,
            )
        )
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return out


async def checklist(conn: asyncpg.Connection, month: date) -> Checklist:
    """Checklist (UX-DR40): saldo PF conferido e transações revisadas sempre aparecem (ok ou
    pendência); depois as outras pendências do mês; e o resumo que vai ser congelado."""
    checks = await run_checks(conn, month)
    codes = {c.code: c for c in checks}
    pf = codes.get("saldo_pf_divergente") or codes.get("saldo_pf_nao_conferido")
    reviewed = codes.get("transacoes_pendentes")
    items = [
        ChecklistItem(
            key="saldo_pf",
            code=pf.code if pf else None,
            ok=pf is None,
            kind=pf.kind if pf else "info",
            message=pf.message if pf else "Saldo da conta PF conferido no fim do mês.",
        ),
        ChecklistItem(
            key="revisadas",
            code=reviewed.code if reviewed else None,
            ok=reviewed is None,
            kind=reviewed.kind if reviewed else "info",
            message=reviewed.message if reviewed else "Todas as transações do mês revisadas.",
        ),
    ]
    shown = {"saldo_pf_divergente", "saldo_pf_nao_conferido", "transacoes_pendentes"}
    items += [
        ChecklistItem(key=c.code, code=c.code, ok=False, kind=c.kind, message=c.message)
        for c in checks
        if c.code not in shown
    ]
    return Checklist(
        month=month,
        items=items,
        blocking=sum(1 for i in items if not i.ok and i.kind == "bloqueia"),
        pending=sum(1 for i in items if not i.ok and i.kind == "confirma"),
        summary=await build_month_summary(conn, month, min(month_end(month), today_brt())),
    )


# --------------------------------------------------------------------------------------------
# Assistente de recuperação (Story 5.8 — FR-7, UX-DR41)
# --------------------------------------------------------------------------------------------

# Fontes que precisam cobrir o fim do mês para o passo Importar (a negociação só traz os dias com
# negócio, então não entra).
_RECOVERY_SOURCES = ("nubank_pf", "nubank_mei", "b3_movimentacao", "b3_consolidado")
_BALANCE_DETAIL = {"conferido": "conferido", "divergente": "divergente", None: "não conferido"}


def recovery_steps(
    periodo: str, *, imported: bool, pending: int, balance: str | None, closed: bool
) -> list[RecoveryStep]:
    """Os 4 passos do mês: feito pelo dado; o primeiro que falta é o atual (único botão)."""
    raw = [
        (
            "importar",
            "Importar",
            imported,
            None,
            f"/visao-geral/painel?periodo={periodo}&importar=1",
        ),
        (
            "revisar",
            "Revisar",
            pending == 0,
            f"{pending} a revisar" if pending else None,
            f"/caixa/transacoes?periodo={periodo}&revisar=todas",
        ),
        (
            "conferir",
            "Conferir",
            balance == "conferido",
            _BALANCE_DETAIL.get(balance, "não conferido"),
            f"/caixa/transacoes?periodo={periodo}",
        ),
        ("fechar", "Fechar", closed, None, None),
    ]
    steps: list[RecoveryStep] = []
    current_taken = False
    for key, label_, done, detail, href in raw:
        if done:
            state = "feito"
        elif not current_taken:
            state, current_taken = "atual", True
        else:
            state = "a_fazer"
        steps.append(RecoveryStep(key=key, label=label_, state=state, detail=detail, href=href))
    return steps


async def recovery(
    conn: asyncpg.Connection, today: date | None = None, *, start: date = MIN_MONTH
) -> Recovery:
    """Trilha do mês seguinte ao bloco retroativo (os meses fechados com origin `retro` desde
    `start`, sem buraco) até o mês anterior a hoje; o mês atual é o primeiro aberto. Some quando a
    trilha inteira está fechada."""
    today = today or today_brt()
    current_month = today.replace(day=1)
    last = date(
        current_month.year - (current_month.month == 1), (current_month.month - 2) % 12 + 1, 1
    )
    states = await month_states(conn, start, last) if last >= start else []
    i = 0
    while i < len(states) and states[i].status != "aberto" and states[i].origin == "retro":
        i += 1
    base_until = month_end(states[i - 1].month) if i > 0 else None
    trail = states[i:]
    pending_months = [m for m in trail if m.status == "aberto"]
    if not pending_months:
        return Recovery(
            active=False, base_until=base_until, message=None, months=[], current=None, steps=[]
        )
    month = pending_months[0].month
    periodo = f"{month:%Y-%m}"
    end = month_end(month)
    sources = {s.key: s for s in await ingest_service.sources(conn, today, with_balances=False)}
    imported = all(
        (src := sources.get(k)) is not None
        and src.updated_until is not None
        and src.updated_until >= end
        for k in _RECOVERY_SOURCES
    )
    codes = {c.code for c in await run_checks(conn, month)}
    if "saldo_pf_divergente" in codes:
        balance: str | None = "divergente"
    elif "saldo_pf_nao_conferido" in codes:
        balance = None
    else:
        balance = "conferido"
    message = "Recupere mês a mês até hoje."
    if base_until is not None:
        message = f"A base vai até {base_until:%d/%m/%Y}. {message}"
    return Recovery(
        active=True,
        base_until=base_until,
        message=message,
        months=[RecoveryMonth(month=s.month, status=s.status) for s in trail],
        current=month,
        steps=recovery_steps(
            periodo,
            imported=imported,
            pending=await ledger_service.pending_in_month(conn, month),
            balance=balance,
            closed=False,
        ),
    )
