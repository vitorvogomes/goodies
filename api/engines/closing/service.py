"""Engine `closing` (camada 5 — AD-8): a única forma de calcular o resumo de um mês.

`build_month_summary(conn, month, as_of)` chama os construtores por mês de `ledger` e `portfolio`
(termos da AD-7) com `as_of` = fim do mês, ou hoje no mês corrente. Mês aberto: ao vivo; o
congelado do fechamento chega na Story 5.3.
"""

from __future__ import annotations

import calendar
import json
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg

from engines.common.dates import today_brt
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


async def _store(
    conn: asyncpg.Connection,
    s: MonthSummary,
    version: int,
    accepted: list[CloseCheck],
    origin: str,
) -> None:
    await conn.execute(
        "INSERT INTO month_closes (month, version, status, coverage, confirmations, origin) "
        "VALUES ($1, $2, 'closed', $3::jsonb, $4::jsonb, $5)",
        s.month,
        version,
        json.dumps(s.coverage),
        json.dumps([c.model_dump() for c in accepted]),
        origin,
    )
    unavailable = {t: "fora_do_resumo" for t in _FUTURE_TERMS}
    if s.taxa_poupanca is None:
        unavailable["taxa_poupanca"] = "sem_receita"
    if s.rentabilidade is None:
        unavailable["rentabilidade"] = "sem_preco"
    await conn.execute(
        """
        INSERT INTO month_summary_totals (month, version, as_of, receitas, trabalho, resgates,
          devolucoes, gastos, investido, resultado_mes, saldo_contas, caixa_corretora,
          valor_investido, patrimonio, aplicado, resultado_investimentos, taxa_poupanca,
          rentabilidade, saldo_conferido, unavailable)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18,
          $19, $20::jsonb)
        """,
        s.month,
        version,
        s.as_of,
        s.receitas,
        s.trabalho,
        s.resgates,
        s.devolucoes,
        s.gastos,
        s.investido,
        s.resultado_mes,
        s.saldo_contas,
        s.caixa_corretora,
        s.valor_investido,
        s.patrimonio,
        s.aplicado,
        s.resultado_investimentos,
        s.taxa_poupanca,
        s.rentabilidade,
        s.saldo_conferido_pf,
        json.dumps(unavailable),
    )
    lines: list[tuple[str, str, str, date | None, Decimal]] = []
    lines += [("receitas", "payer", k, None, v) for k, v in s.receitas_por_pagador.items()]
    lines += [("gastos", "category", k, None, v) for k, v in s.gastos_por_categoria.items()]
    lines += [("valor", "class", k, None, v) for k, v in s.valor_por_classe.items()]
    lines += [("valor", "asset", k, None, v) for k, v in s.asset_ids_value.items()]
    lines += [("fluxo", "class", k, d, v) for (k, d), v in s.flows.items()]
    await conn.executemany(
        "INSERT INTO month_summary_lines "
        "(month, version, metric, dimension_kind, dimension_id, flow_date, value) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
        [(s.month, version, m, kind, dim, d, v) for m, kind, dim, d, v in lines],
    )


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
            "UPDATE month_closes SET dirty = true WHERE month = $1 AND status = 'closed' "
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
