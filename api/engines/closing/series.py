"""Séries mensais dos gráficos do Histórico (Story 9.3 — FR-34, AR25): patrimônio e aplicado (a
partir do primeiro mês fechado; mês com "patrimônio não coberto" vira lacuna, sem interpolação) e
aporte planejado × realizado, com a média 12m do realizado. Mês fechado lê o snapshot; aberto, a
valoração do fim do mês (ou de hoje) e o caixa do ledger."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel

from engines.common.dates import add_months, month_end, today_brt
from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id
from engines.ledger import service as ledger_service
from engines.planning.service import month_plan
from engines.portfolio import calc as portfolio_calc
from engines.portfolio.valuation import valuation_as_of

from .growth import NOT_COVERED
from .service import _frozen, _frozen_planned, latest_close

_CENT = Decimal("0.01")


class SeriesPoint(BaseModel):
    month: date
    source: str  # snapshot | live
    patrimonio: Money | None  # None = patrimônio não coberto (lacuna)
    aplicado: Money | None
    planejado: Money | None  # None = não definido
    realizado: Money
    taxa_poupanca: Pct | None = None  # v2.2: a taxa de poupança do mês (%), linha no Histórico


class Series(BaseModel):
    points: list[SeriesPoint]
    realizado_media12: Money | None  # média dos 12 meses antes de `ate` (marcador)


async def _first_closed(conn: asyncpg.Connection) -> date | None:
    value: date | None = await conn.fetchval(
        "SELECT min(month) FROM month_closes WHERE status = 'closed'"
    )
    return value


async def _point(conn: asyncpg.Connection, owner: str, month: date) -> SeriesPoint:
    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        t, _ = await _frozen(conn, month, close["version"])
        covered = dict(json.loads(close["coverage"])).get("B3") != NOT_COVERED
        return SeriesPoint(
            month=month,
            source="snapshot",
            patrimonio=t["patrimonio"] if covered else None,
            aplicado=t["aplicado"] if covered else None,
            planejado=_frozen_planned(t["budget"]),
            # antes do andamento do aporte (8.7), o realizado do mês é o investimento do mês
            realizado=t["realizado"] if t["realizado"] is not None else t["investido"] or 0,
            taxa_poupanca=t["taxa_poupanca"],
        )
    as_of = min(month_end(month), today_brt())
    valuation = await valuation_as_of(conn, owner, as_of)
    accounts = await ledger_service.accounts_balance(conn, as_of)
    ledger = await ledger_service.ledger_month(conn, month)
    plan = await month_plan(conn, month)
    return SeriesPoint(
        month=month,
        source="live",
        patrimonio=portfolio_calc.patrimony(valuation.invested, accounts=accounts.value),
        aplicado=valuation.contributed,
        planejado=plan.aporte_planejado,
        realizado=ledger.investido,
        taxa_poupanca=(
            (ledger.taxa_poupanca * 100).quantize(_CENT)
            if ledger.taxa_poupanca is not None
            else None
        ),
    )


async def series(conn: asyncpg.Connection, ate: date) -> Series:
    first = await _first_closed(conn)
    if first is None or first > ate:
        return Series(points=[], realizado_media12=None)
    owner = await get_owner_id(conn)
    points: list[SeriesPoint] = []
    month = first
    while month <= ate:
        points.append(await _point(conn, owner, month))
        month = add_months(month, 1)
    # média dos 12 meses antes do período (a mesma janela do Histórico): sem o mês escolhido, que
    # pode estar aberto e parcial
    last12 = [p.realizado for p in points[:-1][-12:]]
    media = (sum(last12, Decimal(0)) / len(last12)).quantize(_CENT) if last12 else None
    return Series(points=points, realizado_media12=media)
