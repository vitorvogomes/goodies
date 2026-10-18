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
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from config import settings
from engines.common.dates import today_brt
from engines.wallet import service as wallet_service
from workers.backup import run_db_backup, run_restore_check
from workers.benchmark_workers import run_benchmark_daily
from workers.price_workers import run_price_b3, run_price_crypto
from workers.wallet_workers import _default_fetchers, resolve_owner_id, run_wallet_scan

_LOCK_KEY = 0x60D1E5  # chave fixa do advisory lock do refresh on-demand


@dataclass(frozen=True)
class JobSpec:
    name: str
    run: Callable[[asyncpg.Pool], Awaitable[dict[str, Any]]]
    threshold_seconds: int
    # idade do DADO (não do heartbeat): se mais velho que last_run, decide o vencimento.
    # Mesmo critério do /jobs/status (wallet_scan envelhece pelo scanned_at real).
    data_since: Callable[[asyncpg.Connection], Awaitable[datetime | None]] | None = None
    # variante do cron (mesmo heartbeat): o catch-up roda `run`; o scheduler roda
    # `cron_run` quando existir (ex.: wallet_scan COM Binance — cron only).
    cron_run: Callable[[asyncpg.Pool], Awaitable[dict[str, Any]]] | None = None
    # vencimento próprio (last_run, now) -> bool; substitui o limiar (ex.: mensal).
    is_due: Callable[[datetime | None, datetime], bool] | None = None
    # vencimento extra, além do limiar (ex.: o scan do último dia do mês).
    extra_due: Callable[[datetime | None, datetime], bool] | None = None
    # "Atualizar tudo" (force) roda o job mesmo fresco? Backup e conferência de restauração não:
    # rodam só no vencimento (cron ou catch-up), nunca a cada clique.
    forceable: bool = True


async def oldest_wallet_scan(conn: asyncpg.Connection) -> datetime | None:
    """scanned_at mais antigo das posições escaneadas (a regra mora em `wallet.service`)."""
    return await wallet_service.oldest_scan(conn)


_BRT = ZoneInfo("America/Sao_Paulo")
_B3_RUN_HOUR = 19


def _last_b3_slot(now: datetime) -> datetime:
    """O último horário de cron do price_b3 (dia útil, 19:00 BRT) até `now`."""
    local = now.astimezone(_BRT)
    slot = local.replace(hour=_B3_RUN_HOUR, minute=0, second=0, microsecond=0)
    if slot > local:
        slot -= timedelta(days=1)
    while slot.weekday() >= 5:  # sábado/domingo: o cron não roda
        slot -= timedelta(days=1)
    return slot


def b3_due(last_run: datetime | None, now: datetime) -> bool:
    """price_b3 vence só quando passou um horário de cron (dia útil 19:00) desde o último run:
    no fim de semana nada vence (e o catch-up não gasta a cota do BRAPI à toa)."""
    return last_run is None or last_run < _last_b3_slot(now)


def month_end_scan_due(last_run: datetime | None, now: datetime) -> bool:
    """No último dia do mês (BRT), o scan de carteiras vence se ainda não rodou nesse dia: o fim de
    cada mês fica com a carteira daquele dia no histórico (Story 5.1)."""
    local = now.astimezone(_BRT).date()
    if (local + timedelta(days=1)).day != 1:
        return False
    return last_run is None or last_run.astimezone(_BRT).date() < local


def job_due(spec: JobSpec, last_run: datetime | None, now: datetime, *, forced: bool) -> bool:
    """Vence: forçado; pelo vencimento próprio; ou pelo limiar — mais o vencimento extra (o scan
    do último dia do mês)."""
    if forced:
        return True
    if spec.is_due is not None:
        return spec.is_due(last_run, now)
    if last_run is None or (now - last_run).total_seconds() >= spec.threshold_seconds:
        return True
    return spec.extra_due is not None and spec.extra_due(last_run, now)


def monthly_due(last_run: datetime | None, now: datetime) -> bool:
    """Vence uma vez por mês civil (BRT): nunca rodou ou rodou antes do dia 1 deste mês."""
    if last_run is None:
        return True
    today = today_brt(now)
    return today_brt(last_run) < today.replace(day=1)


async def _job_db_backup(_pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_db_backup()


async def _job_restore_check(_pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_restore_check()


async def _job_b3(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_price_b3(pool)


async def _job_crypto(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_price_crypto(pool)


async def _wallet_scan(pool: asyncpg.Pool, *, include_binance: bool) -> dict[str, Any]:
    uid = await resolve_owner_id(pool)
    if uid is None:
        return {"skipped": "no_user"}
    return await run_wallet_scan(
        pool, uid, fetchers=_default_fetchers(include_binance=include_binance)
    )


async def _job_wallet(pool: asyncpg.Pool) -> dict[str, Any]:
    """Catch-up on-demand: carteiras sem a Binance (API assinada é cron only)."""
    return await _wallet_scan(pool, include_binance=False)


async def _job_wallet_cron(pool: asyncpg.Pool) -> dict[str, Any]:
    return await _wallet_scan(pool, include_binance=True)


async def _job_benchmark(pool: asyncpg.Pool) -> dict[str, Any]:
    return await run_benchmark_daily(pool)


def stats_partial(stats: Any) -> bool:
    """Run "ok" cujo conteúdo indica falha de fonte: o fail-soft dos workers engole
    exceções e grava ok=true, então `partial` é derivado dos stats — failed>0, fonte
    com símbolos pedidos e zero cotações, ou scan inteiro de mãos vazias."""
    if not isinstance(stats, dict) or not stats:
        return False
    leaves = [v for v in stats.values() if isinstance(v, dict)] or [stats]
    fetch_totals: list[int] = []
    for leaf in leaves:
        symbols = leaf.get("symbols")
        if isinstance(symbols, int) and symbols == 0:
            continue  # nada a buscar nesta fonte: zeros não são falha
        failed = leaf.get("failed")
        fetched = leaf.get("fetched")
        if isinstance(failed, int) and failed > 0:
            return True
        if isinstance(symbols, int) and symbols > 0 and fetched == 0:
            return True
        if isinstance(fetched, int) and isinstance(failed, int):
            fetch_totals.append(fetched)
    # só leaves com a métrica failed (fetchers de wallet) entram no total; um scan
    # em que TODAS as fontes voltaram vazias não pode aparecer como "fresh"
    return bool(fetch_totals) and sum(fetch_totals) == 0


# Quando a API subiu: o aviso de job atrasado espera o catch-up (ou 30 min de máquina ligada).
PROCESS_STARTED = datetime.now(UTC)


def default_jobs() -> list[JobSpec]:
    """Jobs reais + limiares = ttl do cache da fonte (B3 26h, cripto 2h, carteira 14h…)."""
    return [
        JobSpec("price_b3", _job_b3, settings.ttl_b3, is_due=b3_due),
        JobSpec("price_crypto", _job_crypto, settings.ttl_crypto),
        JobSpec(
            "wallet_scan",
            _job_wallet,
            settings.ttl_wallet,
            data_since=oldest_wallet_scan,
            extra_due=month_end_scan_due,
            cron_run=_job_wallet_cron,
        ),
        JobSpec("benchmark", _job_benchmark, settings.ttl_benchmark),
        # Story 1.2 — backup diário do banco local e conferência mensal da restauração.
        JobSpec("db_backup", _job_db_backup, 24 * 3600, forceable=False),
        JobSpec(
            "restore_check",
            _job_restore_check,
            31 * 24 * 3600,
            is_due=monthly_due,
            forceable=False,
        ),
    ]


async def _record(
    conn: asyncpg.Connection,
    job: str,
    now: datetime,
    ok: bool,
    error: str | None,
    stats: dict[str, Any],
) -> None:
    # Sucesso = ok e completo: um "ok" parcial (fonte falhando dentro do fail-soft) não renova
    # `last_success_at`, então o aviso de worker atrasado aparece (Story 4.3).
    success = now if ok and not stats_partial(stats) else None
    await conn.execute(
        "INSERT INTO job_runs (job, last_run, ok, error, stats, last_success_at) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6) "
        "ON CONFLICT (job) DO UPDATE SET "
        "last_run = $2, ok = $3, error = $4, stats = $5::jsonb, "
        "last_success_at = COALESCE($6, job_runs.last_success_at)",
        job,
        now,
        ok,
        error,
        json.dumps(stats, default=str),
        success,
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
    if spec.cron_run is not None:
        spec = replace(spec, run=spec.cron_run)
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
                if not job_due(spec, lr, now, forced=force and spec.forceable):
                    results[spec.name] = "fresh"
                    continue
                ok = await run_and_record(pool, spec, now, lock_conn)
                results[spec.name] = "ok" if ok else "error"
            return {"status": "ran", "jobs": results}
        finally:
            await lock_conn.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_KEY)
