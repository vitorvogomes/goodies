"""Story 4.3 — aviso de worker com falha ou atrasado: só sem sucesso dentro do intervalo do job,
e só depois que o catch-up tentou e falhou ou com 30 min de máquina ligada; some quando o job
volta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from engines.common.alerts import AlertContext
from engines.common.month_status import AllMonthsOpen
from workers import refresh
from workers.job_alerts import BRT, job_alerts


def _ctx() -> AlertContext:
    now = datetime.now(UTC)
    return AlertContext(
        today=now.date(), periodo=now.date().replace(day=1), months=AllMonthsOpen(), owner_id="x"
    )


async def _set(
    pool: Any, job: str, *, last_run: datetime, ok: bool, last_success: datetime | None
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok, error, stats, last_success_at) "
            "VALUES ($1, $2, $3, NULL, '{}'::jsonb, $4) ON CONFLICT (job) DO UPDATE SET "
            "last_run = $2, ok = $3, last_success_at = $4",
            job,
            last_run,
            ok,
            last_success,
        )


@pytest.fixture
async def saved_runs(pool: Any):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM job_runs")
        await conn.execute("DELETE FROM job_runs")
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM job_runs")
        for r in rows:
            await conn.execute(
                "INSERT INTO job_runs (job, last_run, ok, error, stats, last_success_at) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                r["job"],
                r["last_run"],
                r["ok"],
                r["error"],
                r["stats"],
                r["last_success_at"],
            )


@pytest.mark.asyncio
async def test_failed_backup_after_catch_up(pool: Any, saved_runs: None, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(refresh, "PROCESS_STARTED", now - timedelta(minutes=5))
    await _set(
        pool,
        "db_backup",
        last_run=now - timedelta(minutes=1),
        ok=False,
        last_success=now - timedelta(days=3),
    )
    async with pool.acquire() as conn:
        alerts = await job_alerts(conn, _ctx())
    backup = [a for a in alerts if a.key == "job:db_backup"]
    assert (
        backup
        # a data é a de Brasília (perto da meia-noite o dia UTC já virou)
        and backup[0].message
        == f"Backup do banco falhou em {(now - timedelta(minutes=1)).astimezone(BRT):%d/%m/%Y}."
    )
    assert backup[0].action.label == "Ver atualização"


@pytest.mark.asyncio
async def test_late_job_waits_30_minutes_of_uptime(
    pool: Any, saved_runs: None, monkeypatch
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=4)
    await _set(pool, "price_b3", last_run=old, ok=True, last_success=old)
    monkeypatch.setattr(refresh, "PROCESS_STARTED", now - timedelta(minutes=10))
    async with pool.acquire() as conn:
        assert not [a for a in await job_alerts(conn, _ctx()) if a.key == "job:price_b3"]
    monkeypatch.setattr(refresh, "PROCESS_STARTED", now - timedelta(minutes=31))
    async with pool.acquire() as conn:
        late = [a for a in await job_alerts(conn, _ctx()) if a.key == "job:price_b3"]
    assert late and late[0].message.startswith("Preço B3 sem atualização desde ")
    # o job volta a rodar: o aviso some
    await _set(pool, "price_b3", last_run=now, ok=True, last_success=now)
    async with pool.acquire() as conn:
        assert not [a for a in await job_alerts(conn, _ctx()) if a.key == "job:price_b3"]


@pytest.mark.asyncio
async def test_partial_run_does_not_count_as_success(pool: Any, saved_runs: None) -> None:
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await refresh._record(
            conn, "price_b3", now, True, None, {"b3": {"symbols": 17, "fetched": 1, "failed": 16}}
        )
        partial = await conn.fetchval("SELECT last_success_at FROM job_runs WHERE job = 'price_b3'")
        await refresh._record(
            conn, "price_b3", now, True, None, {"b3": {"symbols": 17, "fetched": 17, "failed": 0}}
        )
        full = await conn.fetchval("SELECT last_success_at FROM job_runs WHERE job = 'price_b3'")
    assert partial is None and full == now


def test_router_moved_to_workers() -> None:
    from pathlib import Path

    import workers.router  # noqa: F401

    assert not (Path(__file__).parents[2] / "engines" / "jobs").exists()
