"""E2 — refresh_stale: roda só os vencidos, grava heartbeat, coalesce concorrente."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from workers.refresh import _LOCK_KEY, JobSpec, refresh_stale

_NOW = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)


def _spec(name: str, calls: list[str], *, threshold: int = 3600, fail: bool = False) -> JobSpec:
    async def run(_pool: Any) -> dict[str, Any]:
        calls.append(name)
        if fail:
            raise RuntimeError("boom")
        return {"fetched": 1}

    return JobSpec(name, run, threshold)


async def _clear(pool: Any) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM job_runs")


@pytest.mark.asyncio
async def test_runs_only_due_jobs(pool: Any) -> None:
    await _clear(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('job_a', $1, true)", _NOW
        )
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('job_b', $1, true)",
            _NOW - timedelta(hours=2),  # vencido p/ threshold 1h
        )
    calls: list[str] = []
    specs = [
        _spec("job_a", calls),  # fresco (rodou agora)
        _spec("job_b", calls),  # vencido
        _spec("job_c", calls),  # nunca rodou -> vencido
    ]
    res = await refresh_stale(pool, now=_NOW, jobs=specs)
    assert res["status"] == "ran"
    assert res["jobs"] == {"job_a": "fresh", "job_b": "ok", "job_c": "ok"}
    assert sorted(calls) == ["job_b", "job_c"]


@pytest.mark.asyncio
async def test_force_runs_all(pool: Any) -> None:
    await _clear(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('job_a', $1, true)", _NOW
        )
    calls: list[str] = []
    res = await refresh_stale(pool, now=_NOW, force=True, jobs=[_spec("job_a", calls)])
    assert calls == ["job_a"]
    assert res["jobs"]["job_a"] == "ok"


@pytest.mark.asyncio
async def test_records_error_on_failure(pool: Any) -> None:
    await _clear(pool)
    calls: list[str] = []
    res = await refresh_stale(
        pool, now=_NOW, force=True, jobs=[_spec("job_x", calls, fail=True)]
    )
    assert res["jobs"]["job_x"] == "error"
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT ok, error FROM job_runs WHERE job = 'job_x'")
    assert row["ok"] is False
    assert "RuntimeError" in row["error"]


@pytest.mark.asyncio
async def test_concurrent_refresh_is_coalesced(pool: Any) -> None:
    await _clear(pool)
    calls: list[str] = []
    held = await pool.acquire()
    try:
        await held.fetchval("SELECT pg_advisory_lock($1)", _LOCK_KEY)
        res = await refresh_stale(
            pool, now=_NOW, force=True, jobs=[_spec("job_a", calls)]
        )
        assert res["status"] == "already_running"
        assert calls == []  # nada rodou (lock tomado)
    finally:
        await held.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_KEY)
        await pool.release(held)
