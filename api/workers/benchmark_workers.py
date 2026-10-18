"""Worker benchmark_daily (m4 04-07; catch-up na Story 7.2) — CDI/IPCA do BCB em benchmark_data.

Cron 1x/dia (22h) e catch-up: busca do último ponto gravado (com folga, idempotente) até hoje pelo
intervalo do SGS, então um dia sem rodar não deixa buraco. O SQL mora em `market.service` (AD-1).
Fetcher injetável p/ teste.
"""
from __future__ import annotations

from datetime import date

import asyncpg

from engines.common.dates import today_brt
from engines.market import service as market_service
from engines.market.fetchers.bcb import BcbFetcher, BenchmarkPoint


async def run_benchmark_daily(
    pool: asyncpg.Pool,
    *,
    bcb: BcbFetcher | None = None,
    today: date | None = None,
    start: date | None = None,
) -> dict[str, int]:
    """Busca CDI/IPCA de `start` (padrão: o catch-up) até hoje e grava. {fetched, updated}."""
    bcb = bcb or BcbFetcher()
    today = today or today_brt()
    async with pool.acquire() as conn:
        if start is None:
            start = market_service.benchmark_catchup_start(
                await market_service.benchmark_last_date(conn)
            )
        points: list[BenchmarkPoint] = await bcb.fetch_range(start, today)
        updated = await market_service.upsert_benchmarks(conn, points)
    return {"fetched": len(points), "updated": updated}
