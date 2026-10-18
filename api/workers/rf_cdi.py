"""Job rf_cdi (Story 7.4): o preço de caixinhas e CDBs pelo CDI publicado, depois do benchmark.

Para cada ativo `valuation = 'cdi'` com posição aberta: valor = `rf.cdi_value` (%CDI do ativo
sobre o CDI de benchmark_data até hoje) e preço = valor ÷ quantidade, gravado pelo chokepoint de
preço com a fonte `cdi` (não manual). Sem CDI publicado, ou com o histórico em boa parte faltando
(> 5% dos dias úteis estimados — antes do backfill, P16), não grava: o preço anterior fica e o
stats conta.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import asyncpg

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.market import service as market_service
from engines.portfolio import calc
from engines.portfolio.rf import cdi_value, rf_cdi_assets

MAX_ESTIMATED_SHARE = 0.05  # mais que isso estimado: o histórico está faltando, não grava


async def run_rf_cdi(pool: asyncpg.Pool, *, today: date | None = None) -> dict[str, int]:
    today = today or today_brt()
    updated = incomplete = 0
    async with pool.acquire() as conn:
        assets = await rf_cdi_assets(conn)
        if not assets:
            return {"assets": 0, "updated": 0, "incomplete": 0}
        owner = await get_owner_id(conn)
        ops: dict[str, list[Any]] = defaultdict(list)
        for op in await conn.fetch(
            "SELECT asset_symbol, tipo, quantidade, valor_unitario, data_operacao "
            "FROM asset_operations WHERE user_id = $1 AND asset_symbol = ANY($2::text[]) "
            "ORDER BY data_operacao",
            owner,
            list(assets),
        ):
            ops[op["asset_symbol"]].append(op)
        series = await market_service.cdi_daily(
            conn, min((o[0]["data_operacao"] for o in ops.values() if o), default=today), today
        )
        for symbol, pct in assets.items():
            qty = calc.quantity(ops[symbol])
            if qty <= 0 or not series:
                continue
            value = cdi_value(ops[symbol], today, pct, series)
            if value.estimated_share > MAX_ESTIMATED_SHARE:
                incomplete += 1
                continue
            written = await market_service.upsert_price(
                conn, symbol, float(value.value / qty), source="cdi", is_manual=False
            )
            updated += 1 if written else 0
    # "failed" > 0 marca o run como parcial (histórico de CDI faltando): o aviso de job aparece
    return {
        "assets": len(assets),
        "updated": updated,
        "incomplete": incomplete,
        "failed": incomplete,
    }
