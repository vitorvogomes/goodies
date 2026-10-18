"""P23: histórico diário de preço cripto (CoinGecko, últimos 365 dias) para o bloco cripto ter
preço nas datas passadas; não sobrescreve o que já existe e ignora ticker sem id."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest
import respx

from scripts.ops import backfill_precos_cripto as bf


def test_parse_market_chart_one_point_per_day() -> None:
    payload = {
        "prices": [
            [1717200000000, 350000.0],  # 2024-06-01 00:00 UTC
            [1717243200000, 351000.0],  # 2024-06-01 12:00 UTC (fica o último do dia)
            [1717286400000, 352000.5],  # 2024-06-02
        ]
    }
    assert bf.parse_market_chart(payload) == [
        (date(2024, 6, 1), 351000.0),
        (date(2024, 6, 2), 352000.5),
    ]


@pytest.mark.asyncio
@respx.mock
async def test_backfill_writes_missing_days_only(pool: Any) -> None:
    respx.get(url__startswith="https://api.coingecko.com/api/v3/coins/zz-coin/market_chart").mock(
        return_value=httpx.Response(
            200, json={"prices": [[1717200000000, 10.0], [1717286400000, 11.0]]}
        )
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, is_manual) "
            "VALUES ('ZZCOIN', '2024-06-02', 99, 'coingecko', false)"
        )
        try:
            stats = await bf.backfill(conn, {"ZZCOIN": "zz-coin", "ZZNOID": None}, days=365)
            rows = dict(
                await conn.fetch(
                    "SELECT ref_date, price_brl FROM asset_price_history WHERE ticker = 'ZZCOIN'"
                )
            )
        finally:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = 'ZZCOIN'")
    assert stats == {"ZZCOIN": 1}
    assert rows == {date(2024, 6, 1): 10, date(2024, 6, 2): 99}  # o que existia fica
