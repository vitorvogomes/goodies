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


@pytest.mark.asyncio
async def test_cron_job_records_heartbeat(pool: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # review m4→main: o cron só logava — /jobs/status não via os runs do scheduler e o
    # catch-up re-buscava (gastando quota BRAPI). O cron grava job_runs como o refresh.
    from workers import scheduler

    await _clear(pool)
    calls: list[str] = []
    monkeypatch.setattr(
        "workers.refresh.default_jobs", lambda: [_spec("price_b3", calls)]
    )
    monkeypatch.setattr("workers.scheduler.get_pool", lambda: pool)
    await scheduler._job_price_b3()
    assert calls == ["price_b3"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT ok, stats FROM job_runs WHERE job = 'price_b3'")
    assert row is not None and row["ok"] is True


def test_every_cron_job_maps_to_a_jobspec() -> None:
    # cada job do scheduler grava o heartbeat sob o nome de um JobSpec do catch-up
    from workers.refresh import default_jobs
    from workers.scheduler import CRON_JOB_SPEC, build_scheduler

    spec_names = {s.name for s in default_jobs()}
    cron_ids = {j.id for j in build_scheduler().get_jobs()}
    assert set(CRON_JOB_SPEC) == cron_ids
    assert set(CRON_JOB_SPEC.values()) <= spec_names


@pytest.mark.asyncio
async def test_due_by_data_age_even_if_heartbeat_fresh(pool: Any) -> None:
    # review m4→main: /jobs/status marca wallet_scan stale pela idade do DADO
    # (scanned_at); o catch-up tem de decidir pelo mesmo critério (senão diz "fresh"
    # e nunca roda enquanto a tela mostra "desatualizado").
    await _clear(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('job_w', $1, true)", _NOW
        )
    calls: list[str] = []
    base = _spec("job_w", calls)

    async def old_data(_conn: Any) -> datetime:
        return _NOW - timedelta(hours=5)

    spec = JobSpec(base.name, base.run, base.threshold_seconds, data_since=old_data)
    res = await refresh_stale(pool, now=_NOW, jobs=[spec])
    assert res["jobs"]["job_w"] == "ok"
    assert calls == ["job_w"]


@pytest.mark.asyncio
async def test_catch_up_wallet_scan_skips_binance(
    pool: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Decisão 2026-10-17 (CLAUDE.md "Binance cron only"): o catch-up/"Atualizar tudo"
    # escaneia as carteiras SEM a Binance; só o cron chama a API assinada.
    from engines.market.fetchers.wallets.binance import BinanceFetcher
    from workers import refresh

    seen: dict[str, list[type]] = {}

    async def fake_scan(_pool: Any, _uid: str, *, fetchers: Any = None) -> dict[str, Any]:
        seen["fetchers"] = [type(f) for f in fetchers]
        return {}

    async def fake_owner(_pool: Any) -> str:
        return "u1"

    monkeypatch.setattr(refresh, "run_wallet_scan", fake_scan)
    monkeypatch.setattr(refresh, "resolve_owner_id", fake_owner)
    spec = next(s for s in refresh.default_jobs() if s.name == "wallet_scan")

    await spec.run(pool)  # caminho do catch-up
    assert BinanceFetcher not in seen["fetchers"]
    assert seen["fetchers"]  # as demais fontes continuam

    assert spec.cron_run is not None
    await spec.cron_run(pool)  # caminho do cron
    assert BinanceFetcher in seen["fetchers"]


@pytest.mark.asyncio
async def test_oldest_wallet_scan_ignores_binance(pool: Any) -> None:
    # sem cron local, a linha Binance envelhece; ela não pode deixar o wallet_scan
    # eternamente vencido no catch-up (que nem a atualiza).
    from workers.refresh import oldest_wallet_scan

    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ('zz-oldest@t', 'x') RETURNING id"
        )
        try:
            await conn.execute(
                "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
                "quantity, source, scanned_at) VALUES "
                "($1,'binance','spot','BTC',1,'binance', $2), "
                "($1,'solana','sol1','SOL',1,'solana', $3)",
                uid,
                _NOW - timedelta(days=10),
                _NOW - timedelta(hours=1),
            )
            assert await oldest_wallet_scan(conn) == _NOW - timedelta(hours=1)
        finally:
            await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
            await conn.execute("DELETE FROM users WHERE id = $1", uid)
