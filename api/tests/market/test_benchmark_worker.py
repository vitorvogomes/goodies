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

        self.ranges: list[tuple[date, date]] = []

    async def fetch_range(self, start: date, end: date) -> list[BenchmarkPoint]:
        self.ranges.append((start, end))
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


def test_catchup_start() -> None:
    """Story 7.2: o catch-up recomeça um pouco antes do último ponto gravado (revisão do BCB e o
    IPCA mensal); sem nada gravado, o backfill desde jun/2024."""
    from engines.market.service import BENCHMARK_START, benchmark_catchup_start

    assert benchmark_catchup_start(None) == BENCHMARK_START == date(2024, 6, 1)
    assert benchmark_catchup_start(date(2026, 10, 16)) == date(2026, 9, 6)
    assert benchmark_catchup_start(date(2024, 6, 10)) == BENCHMARK_START


@pytest.mark.asyncio
async def test_worker_fetches_from_catchup_start(pool: Any) -> None:
    from engines.market.service import benchmark_catchup_start

    fake = _FakeBcb([])
    await run_benchmark_daily(pool, bcb=fake, today=date(2026, 10, 18))  # type: ignore[arg-type]
    async with pool.acquire() as conn:
        last = await conn.fetchval(
            "SELECT min(d) FROM (SELECT max(ref_date) d FROM benchmark_data GROUP BY series) x"
        )
    assert fake.ranges == [(benchmark_catchup_start(last), date(2026, 10, 18))]


@pytest.mark.asyncio
async def test_empty_series_restarts_catchup(pool: Any) -> None:
    """Revisão do Épico 7: com uma série sem nenhum ponto (o IPCA falhou no backfill), o catch-up
    volta ao início em vez de seguir do último CDI e nunca buscar o IPCA antigo."""
    from engines.market.service import benchmark_last_date

    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute("DELETE FROM benchmark_data WHERE series IN ('CDI', 'IPCA')")
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('CDI', '2026-10-01', 0.05, 'bcb')"
            )
            assert await benchmark_last_date(conn) is None
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('IPCA', '2026-09-01', 0.4, 'bcb')"
            )
            assert await benchmark_last_date(conn) == date(2026, 9, 1)
        finally:
            await tx.rollback()
