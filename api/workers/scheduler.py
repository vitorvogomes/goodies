"""APScheduler do Market Engine (ADR-003: no processo FastAPI, não Celery).

`build_scheduler()` registra os jobs cron (db_backup e restore_check desde a Story 1.2):
- price_b3: **1x/dia útil, 19:00 America/Sao_Paulo** (após o fechamento da B3) — B3+Tesouro.
- price_crypto: a cada 2h, todo dia.

**Free-tier (importante):** o BRAPI grátis permite **1.000 requisições/mês** e **1 ativo por
requisição** (sem batch). Com ~16 tickers, 1x/dia útil ≈ 350/mês (folgado); 3x/dia estouraria
o limite. Por isso a cadência B3 é diária (preço de fechamento basta p/ XIRR/posições) — o
`ttl_b3` (≈26h) é dimensionado p/ a janela diária. CoinGecko demo: 10k/mês, 1 call/run (batch
de ids) → */2h é trivial. Desvia do default "4h" do CLAUDE.md por causa do limite do free-tier.

Os jobs pegam o pool vivo via `get_pool()` no disparo (pool aberto no lifespan antes do
`scheduler.start()`). `coalesce/max_instances=1` evitam empilhar; com a idempotência dos
workers, re-disparos convergem. Cada disparo grava o heartbeat em `job_runs` (mesmo caminho
do catch-up, `run_named_job`) — o /jobs/status e o catch-up enxergam os runs do cron.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db.connection import get_pool
from workers.refresh import run_named_job

logger = structlog.get_logger()

_JOB_DEFAULTS = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}


# id do job cron -> nome do JobSpec do catch-up (workers/refresh.py) sob o qual o
# heartbeat é gravado em job_runs (o /jobs/status e o catch-up leem esse nome).
CRON_JOB_SPEC = {
    "price_b3": "price_b3",
    "price_crypto": "price_crypto",
    "wallet_scan": "wallet_scan",
    "benchmark_daily": "benchmark",
    "rf_cdi": "rf_cdi",
    "db_backup": "db_backup",
    "restore_check": "restore_check",
}


async def _run(job_id: str) -> None:
    ok = await run_named_job(get_pool(), CRON_JOB_SPEC[job_id], datetime.now(UTC))
    logger.info("worker_run", job=job_id, ok=ok)


async def _job_price_b3() -> None:
    await _run("price_b3")


async def _job_price_crypto() -> None:
    await _run("price_crypto")


async def _job_wallet_scan() -> None:
    await _run("wallet_scan")


async def _job_benchmark_daily() -> None:
    await _run("benchmark_daily")


async def _job_rf_cdi() -> None:
    await _run("rf_cdi")


async def _job_db_backup() -> None:
    await _run("db_backup")


async def _job_restore_check() -> None:
    await _run("restore_check")


def build_scheduler() -> AsyncIOScheduler:
    """Cria o scheduler com os jobs registrados (não inicia — o lifespan faz start)."""
    scheduler = AsyncIOScheduler(job_defaults=_JOB_DEFAULTS)
    scheduler.add_job(
        _job_price_b3,
        # 1x/dia útil após o fechamento (free-tier BRAPI: 1.000 req/mês, 1 ativo/req).
        CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone="America/Sao_Paulo"),
        id="price_b3",
        name="price_b3",
    )
    scheduler.add_job(
        _job_price_crypto,
        CronTrigger(hour="*/2", timezone="America/Sao_Paulo"),
        id="price_crypto",
        name="price_crypto",
    )
    scheduler.add_job(
        _job_wallet_scan,
        # 3x/dia (manhã/tarde/noite); APIs de explorer/exchange têm rate limit generoso.
        CronTrigger(hour="8,14,20", minute=0, timezone="America/Sao_Paulo"),
        id="wallet_scan",
        name="wallet_scan",
    )
    scheduler.add_job(
        _job_benchmark_daily,
        # 1x/dia 22h: BCB publica CDI/IPCA por dia útil (open data, sem quota).
        CronTrigger(hour=22, minute=0, timezone="America/Sao_Paulo"),
        id="benchmark_daily",
        name="benchmark_daily",
    )
    scheduler.add_job(
        _job_rf_cdi,
        # Story 7.4: depois do CDI do dia (22h), o preço de caixinhas e CDBs.
        CronTrigger(hour=22, minute=20, timezone="America/Sao_Paulo"),
        id="rf_cdi",
        name="rf_cdi",
    )
    scheduler.add_job(
        _job_db_backup,
        # Story 1.2: 1x/dia; se o notebook estiver desligado, o catch-up roda ao abrir o app.
        CronTrigger(hour=13, minute=0, timezone="America/Sao_Paulo"),
        id="db_backup",
        name="db_backup",
    )
    scheduler.add_job(
        _job_restore_check,
        # Story 1.2: dia 1 de cada mês — restaura o backup num banco descartável e confere.
        CronTrigger(day=1, hour=13, minute=30, timezone="America/Sao_Paulo"),
        id="restore_check",
        name="restore_check",
    )
    return scheduler


# Story 10.3: o nome do job no catch-up (`refresh.default_jobs`) → o id no scheduler.
_SCHEDULER_ID = {"benchmark": "benchmark_daily"}


def next_runs(now: datetime) -> dict[str, datetime]:
    """A próxima execução de cada job pelo cron registrado (sem iniciar o scheduler)."""
    out: dict[str, datetime] = {}
    jobs = {j.id: j for j in build_scheduler().get_jobs()}
    for name in (
        "price_b3",
        "price_crypto",
        "wallet_scan",
        "benchmark",
        "rf_cdi",
        "db_backup",
        "restore_check",
    ):
        job = jobs.get(_SCHEDULER_ID.get(name, name))
        fire = job.trigger.get_next_fire_time(None, now) if job is not None else None
        if fire is not None:
            out[name] = fire
    return out
