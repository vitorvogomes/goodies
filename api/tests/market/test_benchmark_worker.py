"""Worker benchmark_daily — upsert em benchmark_data (m4 04-07)."""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.market.fetchers.bcb import BenchmarkPoint
from workers.benchmark_workers import run_benchmark_daily

_REF = date(2020, 1, 2)  # data de teste improvável de colidir


class _FakeBcb:
    def __init__(self, points: list[BenchmarkPoint]) -> None:
        self._points = points

    async def fetch(self) -> list[BenchmarkPoint]:
        return self._points


async def _cleanup(pool: Any) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM benchmark_data WHERE ref_date = $1", _REF)


@pytest.mark.asyncio
async def test_writes_benchmark_rows(pool: Any) -> None:
    fake = _FakeBcb(
        [
            BenchmarkPoint("CDI", _REF, 0.05, "bcb"),
            BenchmarkPoint("IPCA", _REF, 0.4, "bcb"),
        ]
    )
    try:
        stats = await run_benchmark_daily(pool, bcb=fake)  # type: ignore[arg-type]
        assert stats == {"fetched": 2, "updated": 2}
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT series, value FROM benchmark_data WHERE ref_date = $1 ORDER BY series",
                _REF,
            )
        assert [(r["series"], float(r["value"])) for r in rows] == [
            ("CDI", 0.05),
            ("IPCA", 0.4),
        ]
    finally:
        await _cleanup(pool)


@pytest.mark.asyncio
async def test_idempotent_rerun_updates_in_place(pool: Any) -> None:
    try:
        await run_benchmark_daily(pool, bcb=_FakeBcb([BenchmarkPoint("CDI", _REF, 0.05, "bcb")]))  # type: ignore[arg-type]
        await run_benchmark_daily(pool, bcb=_FakeBcb([BenchmarkPoint("CDI", _REF, 0.06, "bcb")]))  # type: ignore[arg-type]
        async with pool.acquire() as conn:
            n = await conn.fetchval(
                "SELECT count(*) FROM benchmark_data WHERE series = 'CDI' AND ref_date = $1",
                _REF,
            )
            v = await conn.fetchval(
                "SELECT value FROM benchmark_data WHERE series = 'CDI' AND ref_date = $1",
                _REF,
            )
        assert n == 1  # ON CONFLICT: uma linha só
        assert float(v) == 0.06  # último valor vence
    finally:
        await _cleanup(pool)
