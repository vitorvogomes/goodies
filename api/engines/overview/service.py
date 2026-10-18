"""Painel principal (Story 4.1 — FR-13): monta os KPIs a partir dos termos de `ledger/calc` e
`portfolio/calc` (AD-7), nunca de SQL próprio. Cada número sai em `Valued` com `as_of` = a data
mais antiga das fontes que o geraram.

Transitório (AD-8): até o fechamento (Story 5.2) o `overview` chama direto os construtores de
`ledger` e `portfolio`; patrimônio e rentabilidade de um mês passado esperam o resumo congelado
do fechamento (`antes_do_primeiro_fechamento`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.dates import today_brt
from engines.common.models import Valued
from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.market import service as market_service
from engines.portfolio import calc as portfolio_calc
from engines.portfolio import service as portfolio_service
from engines.wallet import service as wallet_service

from .models import Fonte, Painel

_CLOSED = Valued[Decimal](unavailable_reason="antes_do_primeiro_fechamento")


def _previous(month: date) -> date:
    return date(month.year - 1, 12, 1) if month.month == 1 else month.replace(month=month.month - 1)


async def _month_result(conn: asyncpg.Connection, month: date) -> Valued[Decimal]:
    found = await ledger_service.month_result_for(conn, month)
    if found is None:
        return Valued(unavailable_reason="nao_definido")
    return Valued(value=found.value, as_of=found.as_of, source="ledger")


async def painel(conn: asyncpg.Connection, month: date) -> Painel:
    today = today_brt()
    pending = await ledger_service.pending_review_count(conn)
    resultado = await _month_result(conn, month)
    anterior = await _month_result(conn, _previous(month))
    if month != today.replace(day=1):
        return Painel(
            periodo=f"{month:%Y-%m}",
            resultado_mes=resultado,
            resultado_mes_anterior=anterior,
            patrimonio=_CLOSED,
            resultado_investimentos=_CLOSED,
            rentabilidade_nominal=_CLOSED,
            a_revisar=pending,
        )
    owner = await get_owner_id(conn)
    snap = await portfolio_service.portfolio_snapshot(conn, owner)
    accounts = await ledger_service.accounts_balance(conn, today)
    invested = portfolio_calc.invested_value(
        positions=snap.positions_value, crypto=snap.crypto_value
    )
    dates = [d for d in (snap.as_of, accounts.as_of) if d is not None]
    as_of = min(dates) if dates else None
    xirr = (await portfolio_service.calculate_portfolio_xirr(conn, owner)).get("consolidated")
    return Painel(
        periodo=f"{month:%Y-%m}",
        resultado_mes=resultado,
        resultado_mes_anterior=anterior,
        patrimonio=Valued(
            value=portfolio_calc.patrimony(invested, accounts=accounts.value),
            as_of=as_of,
            source="portfolio",
            stale=snap.stale,
        ),
        resultado_investimentos=Valued(
            value=portfolio_calc.investment_result(
                invested, contributed=snap.contributed, income=snap.income
            ),
            as_of=snap.as_of,
            source="portfolio",
            stale=snap.stale,
        ),
        rentabilidade_nominal=(
            Valued(
                value=Decimal(repr(xirr)) * 100,
                as_of=snap.as_of,
                source="portfolio",
                stale=snap.stale,
            )
            if xirr is not None
            else Valued(unavailable_reason="sem_preco", as_of=snap.as_of, source="portfolio")
        ),
        a_revisar=pending,
    )


# Limites das fontes automáticas: preço diário + fim de semana; scan 2×/dia; CDI dia útil.
_AUTO_LIMIT_DAYS = {"precos": 3, "carteiras": 1, "indices": 5}


async def fontes(conn: asyncpg.Connection) -> list[Fonte]:
    """Bloco Fontes do Painel: as 5 de arquivo (com a conferência da PF) e as automáticas."""
    today = today_brt()
    rows = [
        Fonte(**r.model_dump(), opens_hub=True) for r in await ingest_service.sources(conn, today)
    ]
    prices = await market_service.oldest_market_price(conn)
    scan = await wallet_service.oldest_scan(conn)
    index = await market_service.latest_index_date(conn)
    auto = (
        ("precos", "Preços", prices.date() if prices else None),
        ("carteiras", "Carteiras", scan.date() if scan else None),
        ("indices", "CDI/IPCA", index),
    )
    for key, label, until in auto:
        rows.append(
            Fonte(
                key=key,
                label=label,
                kind="automático",
                updated_until=until,
                stale=until is not None and (today - until).days > _AUTO_LIMIT_DAYS[key],
                opens_hub=False,
            )
        )
    return rows
