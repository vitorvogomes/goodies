"""Engine `closing` (camada 5 — AD-8): a única forma de calcular o resumo de um mês.

`build_month_summary(conn, month, as_of)` chama os construtores por mês de `ledger` e `portfolio`
(termos da AD-7) com `as_of` = fim do mês, ou hoje no mês corrente. Mês aberto: ao vivo; o
congelado do fechamento chega na Story 5.3.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.portfolio import calc as portfolio_calc
from engines.portfolio.valuation import valuation_as_of

from .models import MonthSummary


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
        portfolio_as_of=valuation.data_as_of,
        portfolio_stale=valuation.stale,
        coverage=valuation.coverage,
    )
