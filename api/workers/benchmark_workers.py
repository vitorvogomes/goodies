"""Worker benchmark_daily (m4 04-07) — coleta CDI/IPCA do BCB p/ benchmark_data.

Cron 1x/dia (22h). Idempotente (ON CONFLICT por série+data). IBOV fica p/ o m5
(05-03 via yfinance). O uso pleno (acumulado, retorno real, XIRR vs benchmark) é m5;
aqui nasce só a coleta. Fetcher injetável p/ teste.
"""
from __future__ import annotations

import asyncpg

from engines.market.fetchers.bcb import BcbFetcher, BenchmarkPoint


async def run_benchmark_daily(
    pool: asyncpg.Pool, *, bcb: BcbFetcher | None = None
) -> dict[str, int]:
    """Coleta CDI/IPCA e faz upsert em benchmark_data. Devolve stats {fetched, updated}."""
    bcb = bcb or BcbFetcher()
    points: list[BenchmarkPoint] = await bcb.fetch()
    updated = 0
    async with pool.acquire() as conn:
        for p in points:
            await conn.execute(
                """
                INSERT INTO benchmark_data (series, ref_date, value, source)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (series, ref_date) DO UPDATE
                  SET value = EXCLUDED.value, source = EXCLUDED.source, fetched_at = now()
                """,
                p.series,
                p.ref_date,
                p.value,
                p.source,
            )
            updated += 1
    return {"fetched": len(points), "updated": updated}
