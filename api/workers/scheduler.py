"""APScheduler do Market Engine (ADR-003: no processo FastAPI, não Celery).

`build_scheduler()` registra dois jobs cron (CLAUDE.md):
- price_b3: dias úteis, 9-18h a cada 4h (09/13/17h) — B3 + Tesouro.
- price_crypto: a cada 2h, todo dia.

Os jobs pegam o pool vivo via `get_pool()` no momento do disparo (o pool é aberto no
lifespan antes do `scheduler.start()`). `coalesce/max_instances=1` evitam empilhar
execuções; combinado com a idempotência dos workers, re-disparos convergem.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db.connection import get_pool
from workers.price_workers import run_price_b3, run_price_crypto

logger = logging.getLogger("goodies.workers")

_JOB_DEFAULTS = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}


async def _job_price_b3() -> None:
    stats = await run_price_b3(get_pool())
    logger.info("worker price_b3 ok: %s", stats)


async def _job_price_crypto() -> None:
    stats = await run_price_crypto(get_pool())
    logger.info("worker price_crypto ok: %s", stats)


def build_scheduler() -> AsyncIOScheduler:
    """Cria o scheduler com os jobs registrados (não inicia — o lifespan faz start)."""
    scheduler = AsyncIOScheduler(job_defaults=_JOB_DEFAULTS)
    scheduler.add_job(
        _job_price_b3,
        CronTrigger(day_of_week="mon-fri", hour="9-18/4"),
        id="price_b3",
        name="price_b3",
    )
    scheduler.add_job(
        _job_price_crypto,
        CronTrigger(hour="*/2"),
        id="price_crypto",
        name="price_crypto",
    )
    return scheduler
