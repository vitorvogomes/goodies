"""Engine `closing` (camada 5 — AD-8): a única forma de calcular o resumo de um mês.

`build_month_summary(conn, month, as_of)` chama os construtores por mês de `ledger` e `portfolio`
(termos da AD-7) com `as_of` = fim do mês, ou hoje no mês corrente. `month_summary` é a leitura das
telas: mês aberto, ao vivo; mês fechado, a versão vigente do snapshot, nunca recalculada (5.5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from engines.common.alerts import brl
from engines.common.dates import (
    MIN_MONTH,
    add_months,
    month_end,
    months_between,
    resolve_period,
    today_brt,
)
from engines.common.models import Valued
from engines.common.month_status import MonthState as PortState
from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.planning import allocation as planning_allocation
from engines.planning import goals as planning_goals
from engines.planning import progress as planning_progress
from engines.planning import service as planning_service
from engines.planning.models import MonthBudget
from engines.portfolio import calc as portfolio_calc
from engines.portfolio import positions as positions_service
from engines.portfolio.brokers import broker_cash_as_of
from engines.portfolio.valuation import CRYPTO_ESTIMATED, valuation_as_of

from .checks import label, run_checks
from .models import (
    Checklist,
    ChecklistItem,
    CloseCheck,
    CloseOut,
    MonthSource,
    MonthState,
    MonthSummary,
    OnTheWay,
    PeriodSummary,
    PositionsReport,
    Recovery,
    RecoveryMonth,
    RecoveryStep,
    ReopenOut,
    ReopenPreview,
    ReopenRow,
)


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
    budget = await planning_service.month_budget(conn, month)
    month_ret = await _month_return(conn, month, valuation, as_of)
    progress = await planning_progress.month_progress(conn, month)
    planned = progress.planned
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
        consumido=budget.consumido.value or Decimal(0),
        disponivel=budget.disponivel.value or Decimal(0),
        restante=budget.restante.value or Decimal(0),
        restante_sem_resgates=budget.restante_sem_resgates.value or Decimal(0),
        consumo_financiado=budget.consumo_financiado.value or Decimal(0),
        budget=budget,
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
        rentabilidade_mes=month_ret.nominal.value,
        rentabilidade_mes_real=month_ret.real.value,
        valor_por_classe=valuation.by_class,
        valor_por_ativo=valuation.by_asset,
        asset_ids_value=valuation.by_asset_id,
        flows=valuation.flows,
        caixa_corretora=valuation.broker_cash,
        a_caminho=valuation.on_the_way,
        portfolio_as_of=valuation.data_as_of,
        portfolio_stale=valuation.stale,
        coverage=valuation.coverage,
        aporte_planejado=planned,
        realizado=progress.realizado,
        pendente=max(Decimal(0), (planned or Decimal(0)) - progress.realizado),
        realizado_por_classe=progress.by_class,
        realizado_por_ativo=progress.by_asset,
        # o motivo de verdade de cada rentabilidade do mês que falta (sem_preco, aguardando_ipca…)
        unavailable={
            term: v.unavailable_reason
            for term, v in (
                ("rentabilidade_mes", month_ret.nominal),
                ("rentabilidade_mes_real", month_ret.real),
            )
            if v.value is None and v.unavailable_reason
        },
    )


# --------------------------------------------------------------------------------------------
# Fechar o mês: precondições, snapshot e versões (Story 5.3 — FR-32)
# --------------------------------------------------------------------------------------------

# Termos da AD-7 sem engine ainda: congelados nulos com o motivo (AD-8). Desde a Story 8.7, todos
# têm engine (realizado e pendente vêm de `planning`).
_FUTURE_TERMS: tuple[str, ...] = ()


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
    origin: str | None = None,
) -> CloseOut:
    """Fecha o mês: recusa com bloqueio; pede "fechar mesmo assim" das `confirma` (fica gravado);
    grava a versão seguinte com o resumo de `build_month_summary` (as_of = fim do mês). Fechar de
    novo mantém a origem da versão anterior (um mês retroativo continua `retro`)."""
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
        origin = origin or (last["origin"] if last is not None else "live")
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
    "consumido",
    "realizado",
    "pendente",
    "disponivel",
    "restante",
    "restante_sem_resgates",
    "consumo_financiado",
    "a_caminho",
)
_PCT = ("taxa_poupanca", "rentabilidade", "rentabilidade_mes", "rentabilidade_mes_real")
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
    "rentabilidade_mes": "Rentabilidade do mês (% a.a.)",
    "rentabilidade_mes_real": "Rentabilidade real do mês (% a.a.)",
    "consumido": "Consumido",
    "disponivel": "Disponível para consumo",
    "restante": "Restante",
    "restante_sem_resgates": "Restante sem os resgates",
    "consumo_financiado": "Consumo financiado por resgate",
    "realizado": "Aporte realizado",
    "pendente": "Aporte pendente",
    "a_caminho": "A caminho",
}
_CENT = Decimal("0.01")

Line = tuple[str, str, str, date | None, Decimal]


def _totals(s: MonthSummary) -> tuple[dict[str, Any], dict[str, str]]:
    totals: dict[str, Any] = {t: getattr(s, t) for t in _MONEY}
    totals["taxa_poupanca"] = s.taxa_poupanca
    totals["rentabilidade"] = s.rentabilidade
    totals["rentabilidade_mes"] = s.rentabilidade_mes
    totals["rentabilidade_mes_real"] = s.rentabilidade_mes_real
    totals["saldo_conferido"] = s.saldo_conferido_pf
    unavailable = {t: "fora_do_resumo" for t in _FUTURE_TERMS}
    if s.aporte_planejado is None:  # sem aporte planejado, não há pendente
        totals["pendente"] = None
        unavailable["pendente"] = "nao_definido"
    if s.taxa_poupanca is None:
        unavailable["taxa_poupanca"] = "sem_receita"
    if s.rentabilidade is None:
        unavailable["rentabilidade"] = "sem_preco"
    if s.rentabilidade_mes is None:
        unavailable["rentabilidade_mes"] = s.unavailable.get(
            "rentabilidade_mes", "antes_do_primeiro_fechamento"
        )
    if s.rentabilidade_mes_real is None:
        unavailable["rentabilidade_mes_real"] = s.unavailable.get(
            "rentabilidade_mes_real", "aguardando_ipca"
        )
    return totals, unavailable


def _budget_json(budget: MonthBudget | None) -> str | None:
    """Money/Decimal em texto (o Money não aceita float de volta)."""
    return json.dumps(budget.model_dump(), default=str) if budget is not None else None


def _lines(s: MonthSummary) -> list[Line]:
    lines: list[Line] = []
    lines += [("receitas", "payer", k, None, v) for k, v in s.receitas_por_pagador.items()]
    lines += [("gastos", "category", k, None, v) for k, v in s.gastos_por_categoria.items()]
    lines += [("valor", "class", k, None, v) for k, v in s.valor_por_classe.items()]
    lines += [("valor", "asset", k, None, v) for k, v in s.asset_ids_value.items()]
    lines += [("fluxo", "class", k, d, v) for (k, d), v in s.flows.items()]
    lines += [("realizado", "class", k, None, v) for k, v in s.realizado_por_classe.items()]
    lines += [("realizado", "asset", k, None, v) for k, v in s.realizado_por_ativo.items()]
    return lines


async def _store(
    conn: asyncpg.Connection,
    s: MonthSummary,
    version: int,
    accepted: list[CloseCheck],
    origin: str,
) -> None:
    totals, unavailable = _totals(s)
    coverage = dict(s.coverage)
    if origin == "retro":
        _retro_adjust(unavailable, coverage)
    await _write_version(
        conn,
        s.month,
        version,
        as_of=s.as_of,
        totals=totals,
        unavailable=unavailable,
        lines=_lines(s),
        coverage=coverage,
        budget=_budget_json(s.budget),
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
    budget: str | None = None,
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
    n = 4 + len(columns)
    await conn.execute(
        f"INSERT INTO month_summary_totals (month, version, as_of, {', '.join(columns)}, "
        f"unavailable, budget) VALUES ($1, $2, $3, "
        + ", ".join(f"${i}" for i in range(4, n))
        + f", ${n}::jsonb, ${n + 1}::jsonb)",
        month,
        version,
        as_of,
        *[totals.get(c) for c in columns],
        json.dumps(unavailable),
        budget,
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


def _retro_adjust(unavailable: dict[str, str], coverage: dict[str, str]) -> None:
    """Regras do retroativo (Story 5.7), aplicadas em toda versão de um mês `retro`: aporte
    planejado/pendente `nao_definido`; sem consolidado B3, "patrimônio não coberto"."""
    unavailable.update({t: "nao_definido" for t in _RETRO_UNDEFINED})
    if not coverage.get("B3", "").startswith("consolidado"):
        coverage["B3"] = "patrimônio não coberto"


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
        await planning_service.ensure_month_plan(conn, month, mode="retro")
        summary = await build_month_summary(conn, month, month_end(month))
        await _store(conn, summary, 1, accepted, "retro")
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
    real_mes = t["rentabilidade_mes_real"]
    if real_mes is None and t["rentabilidade_mes"] is not None:
        # fechado antes de o IPCA do mês sair: a real sai na leitura, sobre a nominal congelada
        ipca, _ = await _ipca(conn, [month])
        if ipca is not None:
            days = (as_of - (month - timedelta(days=1))).days
            nominal = float(t["rentabilidade_mes"]) / 100
            real_mes = _pct(portfolio_calc.real_rate(nominal, ipca, days))
            unavailable.pop("rentabilidade_mes_real", None)
    return MonthSummary(
        month=month,
        as_of=as_of,
        source="snapshot",
        **money,
        taxa_poupanca=t["taxa_poupanca"],
        rentabilidade=t["rentabilidade"],
        rentabilidade_mes=t["rentabilidade_mes"],
        rentabilidade_mes_real=real_mes,
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
        aporte_planejado=_frozen_planned(t["budget"]),
        realizado_por_classe=by.get(("realizado", "class"), {}),
        realizado_por_ativo=by.get(("realizado", "asset"), {}),
    )


def _frozen_planned(budget: str | None) -> Decimal | None:
    """O aporte planejado congelado no orçamento da versão (antes do orçamento: None)."""
    if not budget:
        return None
    data = json.loads(budget)
    return Decimal(str(data["aporte_planejado"])) if data.get("aporte_definido") else None


async def month_summary(conn: asyncpg.Connection, month: date) -> MonthSummary:
    """Leitura das telas (AD-8): mês fechado → versão vigente do snapshot; aberto → ao vivo."""
    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        return await _snapshot_summary(conn, close)
    return await build_month_summary(conn, month)


async def month_result(conn: asyncpg.Connection, month: date) -> ledger_service.DatedAmount | None:
    """Só o resultado do mês (barato — a variação do Painel): fechado → o congelado; aberto →
    `ledger/calc.month_result`. Sem dado → None."""
    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        row = await conn.fetchrow(
            "SELECT resultado_mes, as_of FROM month_summary_totals "
            "WHERE month = $1 AND version = $2",
            month,
            close["version"],
        )
        if row is not None and row["resultado_mes"] is not None:
            return ledger_service.DatedAmount(row["resultado_mes"], row["as_of"])
        return None
    return await ledger_service.month_result_for(conn, month)


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
        if close["origin"] == "retro":  # Story 6.8: o plano do mês retroativo, pelo serviço
            await planning_service.ensure_month_plan(conn, month, mode="retro")
        live = await build_month_summary(conn, month, month_end(month))
        live_totals, live_unavailable = _totals(live)
        confirmations = list(json.loads(close["confirmations"]))
        budget = _budget_json(live.budget)
        if mode == "recalcular":
            totals, unavailable, lines = live_totals, live_unavailable, _lines(live)
            coverage, dirty = dict(live.coverage), False
            if close["origin"] == "retro":
                _retro_adjust(unavailable, coverage)
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
            # os motivos congelados ficam (inclusive os do retroativo); o que foi preenchido agora
            # leva o motivo de agora
            unavailable = {t: r for t, r in was.items() if t not in missing}
            unavailable.update({t: r for t, r in live_unavailable.items() if t in missing})
            lines = [
                (r["metric"], r["dimension_kind"], r["dimension_id"], r["flow_date"], r["value"])
                for r in frozen_lines
            ]
            have = {(m, kind) for m, kind, *_ in lines}
            lines += [ln for ln in _lines(live) if (ln[0], ln[1]) not in have]
            coverage = {**live.coverage, **dict(json.loads(close["coverage"]))}
            dirty = close["dirty"]
            if frozen["budget"] is not None:  # o orçamento já congelado fica
                budget = frozen["budget"]
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
            budget=budget,
        )
    # o JSON guarda o Money como número: volta por texto (Money não aceita float)
    accepted = [
        CloseCheck(**{**c, "amount": str(c["amount"]) if c.get("amount") is not None else None})
        for c in confirmations
    ]
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
        month = add_months(month, 1)
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
            f"/caixa/transacoes?periodo={periodo}&revisar=mes",
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
    last = add_months(today, -1)
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


# --------------------------------------------------------------------------------------------
# Orçamento do mês (Story 6.5 — AD-8: a leitura do mês passa por `closing`)
# --------------------------------------------------------------------------------------------


async def month_budget(conn: asyncpg.Connection, month: date) -> MonthBudget:
    """O orçamento pelos termos de `planning`; mês fechado → os termos congelados no snapshot (o que
    não existia quando o mês fechou sai `fora_do_resumo`)."""
    budget = await planning_service.month_budget(conn, month)
    close = await latest_close(conn, month)
    if close is None or close["status"] != "closed":
        return budget
    frozen, _ = await _frozen(conn, month, close["version"])
    if frozen["budget"] is not None:  # a Conta inteira congelada
        return MonthBudget.model_validate(
            {**json.loads(frozen["budget"]), "source": "snapshot", "closed": True}
        )
    # snapshot anterior ao orçamento: só os totais congelados; o detalhe não existia
    reasons = dict(json.loads(frozen["unavailable"]))
    update: dict[str, Any] = {"source": "snapshot", "as_of": frozen["as_of"]}
    for term in (
        "disponivel",
        "consumido",
    "realizado",
    "pendente",
        "restante",
        "consumo_financiado",
        "restante_sem_resgates",
        "trabalho",
        "resgates",
    ):
        value = frozen[term]
        update[term] = (
            Valued[Decimal](value=value, as_of=frozen["as_of"], source="snapshot")
            if value is not None
            else Valued[Decimal](unavailable_reason=reasons.get(term, "fora_do_resumo"))
        )
    update.update(
        detalhe=False,
        custos_fixos=Valued[Decimal](unavailable_reason="fora_do_resumo"),
        trabalho_por_pagador=[],
        resgates_itens=[],
        consumido_por_grupo=[],
    )
    return budget.model_copy(update=update)


# --------------------------------------------------------------------------------------------
# Período e Posições (Story 7.1 — AD-8: a leitura de um período passa por `closing`)
# --------------------------------------------------------------------------------------------

_PERIOD_TERMS = (
    "receitas",
    "trabalho",
    "resgates",
    "devolucoes",
    "gastos",
    "investido",
    "resultado_mes",
    "consumido",
    "realizado",
    "pendente",
)


async def period_months(conn: asyncpg.Connection, months: list[date]) -> list[MonthSource]:
    """A fonte de cada mês: fechado → snapshot; aberto → ao vivo."""
    if not months:
        return []
    states = await month_states(conn, months[0], months[-1])
    wanted = set(months)
    return [
        MonthSource(month=s.month, source="live" if s.status == "aberto" else "snapshot")
        for s in states
        if s.month in wanted
    ]


async def build_period_summary(conn: asyncpg.Connection, months: list[date]) -> PeriodSummary:
    """Soma os termos de fluxo dos meses (cada um pela leitura do mês: snapshot ou ao vivo)."""
    totals = dict.fromkeys(_PERIOD_TERMS, Decimal(0))
    sources: list[MonthSource] = []
    for month in sorted(months):
        s = await month_summary(conn, month)
        sources.append(MonthSource(month=month, source=s.source))
        for term in _PERIOD_TERMS:
            totals[term] += getattr(s, term)
    return PeriodSummary(months=sources, **totals)


async def positions(conn: asyncpg.Connection, periodo: str, leitura: str) -> PositionsReport:
    """Posições: aplicado e valor no fim do mês do período; resultado do período da leitura."""
    months = resolve_period(periodo, leitura)
    end = months[-1]
    start = None if leitura == "inicio" else months[0]
    owner = await get_owner_id(conn)
    # Story 8.3: ativos de objetivos num bloco à parte; alocação × meta pelas metas do mês
    linked = frozenset(await planning_goals.linked_assets(conn))
    classes = await positions_service.positions_period(conn, owner, start, end, set_aside=linked)
    await planning_allocation.apply_allocation(conn, classes, end)
    if leitura == "inicio":
        ret = await period_return(conn, months)  # desde jul/2024: o valor de jun/2024 não existe
        summary = await month_summary(conn, end)
        if summary.rentabilidade is not None:  # consolidado desde o início (o XIRR de sempre)
            real = await real_since_start(conn, summary.rentabilidade, end)  # o mesmo do Painel
            ret = PeriodReturn(
                Valued[Decimal](value=summary.rentabilidade, as_of=summary.as_of, source="xirr"),
                real,
                ret.by_class,
                real.as_of,
            )
    else:
        ret = await period_return(conn, months)
    for c in classes:
        if c.key in ret.by_class:
            c.xirr_nominal, c.xirr_real = ret.by_class[c.key]
    brokers = await broker_cash_as_of(conn, owner, min(month_end(end), today_brt()))
    cash = sum((b.caixa for b in brokers), Decimal(0))
    return PositionsReport(
        caixa_corretora=cash,
        total=sum((c.valor for c in classes), Decimal(0)) + cash,
        a_caminho=[
            OnTheWay(broker=b.name, value=b.a_caminho, import_from=b.import_from)
            for b in brokers
            if b.a_caminho > 0
        ],
        periodo=periodo,
        leitura=leitura,
        as_of=min(month_end(end), today_brt()),
        months=await period_months(conn, months),
        classes=classes,
        aplicado=sum((c.aplicado or Decimal(0) for c in classes), Decimal(0)),
        valor=sum((c.valor for c in classes), Decimal(0)),
        xirr_nominal=ret.nominal,
        xirr_real=ret.real,
        ipca_ate=ret.ipca_ate,
    )


# --------------------------------------------------------------------------------------------
# Rentabilidade de um período, nominal × real (Story 7.3 — XIRR sobre o valor investido)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PeriodReturn:
    nominal: Valued[Decimal]
    real: Valued[Decimal]
    by_class: dict[str, tuple[Valued[Decimal], Valued[Decimal]]]
    ipca_ate: date | None


def _pct(rate: float | None) -> Decimal | None:
    return (Decimal(repr(rate)) * 100).quantize(Decimal("0.01")) if rate is not None else None


async def _class_values_at(
    conn: asyncpg.Connection, month: date
) -> tuple[dict[str, Decimal], frozenset[str]] | None:
    """Valor investido por classe no fim do mês: o snapshot se fechado; senão a valoração do
    portfolio naquela data (sem montar o resumo inteiro). Antes de jul/2024 → None. Junto, as
    classes que valiam uma estimativa (o bloco cripto pelo aplicado, sem preço histórico)."""
    if month < MIN_MONTH:
        return None
    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        _, lines = await _frozen(conn, month, close["version"])
        coverage = dict(json.loads(close["coverage"]))
        values = {
            r["dimension_id"]: r["value"]
            for r in lines
            if r["metric"] == "valor" and r["dimension_kind"] == "class"
        }
    else:
        owner = await get_owner_id(conn)
        valuation = await valuation_as_of(conn, owner, month_end(month))
        coverage, values = valuation.coverage, dict(valuation.by_class)
    estimated = frozenset({"cripto"} if coverage.get("cripto") == CRYPTO_ESTIMATED else set())
    return values, estimated


async def _ipca(conn: asyncpg.Connection, months: list[date]) -> tuple[Decimal | None, date | None]:
    """IPCA efetivo dos meses (fator) e o Carimbo: o fim do último mês usado; faltando o do último
    → fator None e o fim do último mês publicado (o que se espera)."""
    from engines.market import service as market_service

    found = await market_service.ipca_monthly(conn, months[0], months[-1])
    if any(m not in found for m in months):
        published = await conn.fetchval(
            "SELECT max(ref_date) FROM benchmark_data WHERE series = 'IPCA'"
        )
        return None, month_end(published) if published is not None else None
    return portfolio_calc.ipca_factor(found[m] for m in months), month_end(months[-1])


def _returns(
    start: dict[str, Decimal],
    start_day: date,
    flows: dict[tuple[str, date], Decimal],
    end: dict[str, Decimal],
    end_day: date,
    ipca: Decimal | None,
    ipca_last: date | None,
    estimated: frozenset[str] = frozenset(),
) -> PeriodReturn:
    """`estimated`: classes cujo valor no início é estimativa (o bloco cripto pelo aplicado, sem
    preço histórico) — saem do consolidado e ficam `sem_preco` (o retorno seria fabricado)."""
    days = (end_day - start_day).days
    if estimated:
        start = {k: v for k, v in start.items() if k not in estimated}
        flows = {k: v for k, v in flows.items() if k[0] not in estimated}
        end = {k: v for k, v in end.items() if k not in estimated}

    def pair(s: Decimal, f: list[tuple[date, Decimal]], e: Decimal) -> tuple[Any, Any]:
        rate = portfolio_calc.period_xirr(s, start_day, f, e, end_day)
        if rate is None:
            nominal = Valued[Decimal](unavailable_reason="sem_preco", as_of=end_day)
            return nominal, Valued[Decimal](unavailable_reason="sem_preco", as_of=end_day)
        nominal = Valued[Decimal](value=_pct(rate), as_of=end_day, source="xirr")
        if ipca is None:
            real = Valued[Decimal](unavailable_reason="aguardando_ipca", as_of=ipca_last)
        else:
            real_rate = portfolio_calc.real_rate(rate, ipca, days)
            real = Valued[Decimal](value=_pct(real_rate), as_of=ipca_last, source="ipca")
        return nominal, real

    classes = set(start) | set(end) | {c for c, _ in flows}
    by_date: dict[date, Decimal] = {}
    for (_, d), v in flows.items():
        by_date[d] = by_date.get(d, Decimal(0)) + v
    nominal, real = pair(
        sum(start.values(), Decimal(0)), sorted(by_date.items()), sum(end.values(), Decimal(0))
    )
    by_class = {
        c: pair(
            start.get(c, Decimal(0)),
            sorted((d, v) for (k, d), v in flows.items() if k == c),
            end.get(c, Decimal(0)),
        )
        for c in classes
    }
    for c in estimated:
        none = Valued[Decimal](unavailable_reason="sem_preco", as_of=end_day)
        by_class[c] = (none, none)
    return PeriodReturn(nominal, real, by_class, ipca_last)


def _unavailable_return(reason: str) -> PeriodReturn:
    none = Valued[Decimal](unavailable_reason=reason)
    return PeriodReturn(none, none, {}, None)


async def _month_return(
    conn: asyncpg.Connection, month: date, valuation: Any, as_of: date
) -> PeriodReturn:
    """XIRR do mês para o resumo: fim do mês anterior → fim do mês (ou hoje)."""
    found = await _class_values_at(conn, add_months(month, -1))
    if found is None:
        return _unavailable_return("antes_do_primeiro_fechamento")
    start, estimated = found
    ipca, last = await _ipca(conn, [month])
    return _returns(
        start,
        month - timedelta(days=1),
        valuation.flows,
        valuation.by_class,
        as_of,
        ipca,
        last,
        estimated,
    )


async def period_return(conn: asyncpg.Connection, months: list[date]) -> PeriodReturn:
    """XIRR do período: valor no fim do mês anterior (snapshot ou valoração), os fluxos líquidos
    datados de cada mês (snapshot ou ao vivo) e o valor no fim; o real desconta o IPCA efetivo."""
    found = await _class_values_at(conn, add_months(months[0], -1))
    if found is None:
        return _unavailable_return("antes_do_primeiro_fechamento")
    start, estimated = found
    flows: dict[tuple[str, date], Decimal] = {}
    end: dict[str, Decimal] = {}
    end_day = months[-1]
    for month in months:
        s = await month_summary(conn, month)
        for key, value in s.flows.items():
            flows[key] = flows.get(key, Decimal(0)) + value
        end, end_day = dict(s.valor_por_classe), s.as_of
    ipca, last = await _ipca(conn, months)
    return _returns(
        start, months[0] - timedelta(days=1), flows, end, end_day, ipca, last, estimated
    )


async def real_since_start(
    conn: asyncpg.Connection, nominal_pct: Decimal | None, month: date
) -> Valued[Decimal]:
    """Rentabilidade real desde o início (Painel): a nominal desde o início descontada do IPCA
    anualizado de jul/2024 até o último mês publicado. Sem o IPCA do mês anterior ao período →
    `aguardando_ipca`; o `as_of` é o mês do IPCA (o carimbo do cartão)."""
    if nominal_pct is None:
        return Valued[Decimal](unavailable_reason="sem_preco")
    months = [m for m in months_between(MIN_MONTH, add_months(month, -1))]
    if not months:
        return Valued[Decimal](unavailable_reason="antes_do_primeiro_fechamento")
    factor, last = await _ipca(conn, months)
    if factor is None:
        return Valued[Decimal](unavailable_reason="aguardando_ipca", as_of=last, source="ipca")
    days = (month_end(months[-1]) - MIN_MONTH).days + 1
    real = portfolio_calc.real_rate(float(nominal_pct) / 100, factor, days)
    return Valued[Decimal](value=_pct(real), as_of=last, source="ipca")
