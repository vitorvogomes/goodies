"""Catch-up local: roda só os jobs vencidos quando o app abre / no botão Atualizar tudo.

Modelo (Pilar 0): o app é local-on-demand, então o cron por horário não dispara. Em vez
disso, `refresh_stale` consulta o heartbeat (`job_runs.last_run`), roda os jobs cujo último
run passou do limiar (= ttl do cache da fonte), grava ok/error/stats, e usa um advisory lock
para que dois refreshes simultâneos não se atropelem (coalescido). Os workers já são
fail-soft e idempotentes; um job que falha não derruba os outros.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from config import settings
from workers.benchmark_workers import run_benchmark_daily
from workers.price_workers import run_price_b3, run_price_crypto
from workers.wallet_workers import resolve_owner_id, run_wallet_scan

_LOCK_KEY = 0x60D1E5  # chave fixa do advisory lock do refresh on-demand


@dataclass(frozen=True)
class JobSpec:
    name: str
    run: Callable[[asyncpg.Pool], Awaitable[dict[str, Any]]]
    threshold_seconds: int
    # idade do DADO (não do heartbeat): se mais velho que last_run, decide o vencimento.
    # Mesmo critério do /jobs/status (wallet_scan envelhece pelo scanned_at real).
    data_since: Callable[[asyncpg.Connection], Awaitable[datetime | None]] | None = None


async def oldest_wallet_scan(conn: asyncpg.Connection) -> datetime | None:
    """scanned_at mais antigo das posições escaneadas (idade real do dado de carteira)."""
    value: datetime | None = await conn.fetchval(
        "SELECT MIN(scanned_at) FROM wallet_positions WHERE NOT is_manual"
    )
    return value


async def _job_b3(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_price_b3(pool)


async def _job_crypto(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_price_crypto(pool)


async def _job_wallet(pool: asyncpg.Pool) -> dict[str, Any]:
    uid = await resolve_owner_id(pool)
    if uid is None:
        return {"skipped": "no_user"}
    return await run_wallet_scan(pool, uid)


async def _job_benchmark(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_benchmark_daily(pool)


def default_jobs() -> list[JobSpec]:
    """Jobs reais + limiares = ttl do cache da fonte (B3 26h, cripto 2h, carteira 14h…)."""
    return [
        JobSpec("price_b3", _job_b3, settings.ttl_b3),
        JobSpec("price_crypto", _job_crypto, settings.ttl_crypto),
        JobSpec("wallet_scan", _job_wallet, settings.ttl_wallet, oldest_wallet_scan),
        JobSpec("benchmark", _job_benchmark, settings.ttl_benchmark),
    ]


async def _record(
    conn: asyncpg.Connection,
    job: str,
    now: datetime,
    ok: bool,
    error: str | None,
    stats: dict[str, Any],
) -> None:
    await conn.execute(
        "INSERT INTO job_runs (job, last_run, ok, error, stats) "
        "VALUES ($1, $2, $3, $4, $5::jsonb) "
        "ON CONFLICT (job) DO UPDATE SET "
        "last_run = $2, ok = $3, error = $4, stats = $5::jsonb",
        job,
        now,
        ok,
        error,
        json.dumps(stats, default=str),
    )


async def run_and_record(
    pool: asyncpg.Pool, spec: JobSpec, now: datetime, conn: asyncpg.Connection | None = None
) -> bool:
    """Roda um job (fail-soft) e grava o heartbeat em job_runs. Usado pelo catch-up e
    pelo cron — assim /jobs/status enxerga os dois caminhos. Devolve ok."""
    ok = True
    error: str | None = None
    stats: dict[str, Any] = {}
    try:
        stats = await spec.run(pool)
    except Exception as exc:  # fail-soft: um job não derruba os outros
        ok, error = False, f"{type(exc).__name__}: {exc}"
    if conn is not None:
        await _record(conn, spec.name, now, ok, error, stats)
    else:
        async with pool.acquire() as own:
            await _record(own, spec.name, now, ok, error, stats)
    return ok


async def run_named_job(pool: asyncpg.Pool, name: str, now: datetime) -> bool:
    """Roda o JobSpec `name` de `default_jobs()` gravando o heartbeat (entrada do cron)."""
    spec = next(s for s in default_jobs() if s.name == name)
    return await run_and_record(pool, spec, now)


async def refresh_stale(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    force: bool = False,
    jobs: list[JobSpec] | None = None,
) -> dict[str, Any]:
    """Roda os jobs vencidos (ou todos, se `force`). Coalescido por advisory lock:
    um 2º refresh concorrente devolve `already_running` sem rodar nada."""
    specs = jobs if jobs is not None else default_jobs()
    async with pool.acquire() as lock_conn:
        got = await lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_KEY)
        if not got:
            return {"status": "already_running", "jobs": {}}
        try:
            last = {
                r["job"]: r["last_run"]
                for r in await lock_conn.fetch("SELECT job, last_run FROM job_runs")
            }
            results: dict[str, str] = {}
            for spec in specs:
                lr = last.get(spec.name)
                if lr is not None and spec.data_since is not None:
                    since = await spec.data_since(lock_conn)
                    if since is not None and since < lr:
                        lr = since  # dado mais velho que o heartbeat (fonte falhando)
                due = (
                    force
                    or lr is None
                    or (now - lr).total_seconds() >= spec.threshold_seconds
                )
                if not due:
                    results[spec.name] = "fresh"
                    continue
                ok = await run_and_record(pool, spec, now, lock_conn)
                results[spec.name] = "ok" if ok else "error"
            return {"status": "ran", "jobs": results}
        finally:
            await lock_conn.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_KEY)
