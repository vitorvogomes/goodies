"""APScheduler do Market Engine (ADR-003: no processo FastAPI, não Celery).

`build_scheduler()` registra dois jobs cron:
- price_b3: **1x/dia útil, 19:00 America/Sao_Paulo** (após o fechamento da B3) — B3+Tesouro.
- price_crypto: a cada 2h, todo dia.

**Free-tier (importante):** o BRAPI grátis permite **1.000 requisições/mês** e **1 ativo por
requisição** (sem batch). Com ~16 tickers, 1x/dia útil ≈ 350/mês (folgado); 3x/dia estouraria
o limite. Por isso a cadência B3 é diária (preço de fechamento basta p/ XIRR/posições) — o
`ttl_b3` (≈26h) é dimensionado p/ a janela diária. CoinGecko demo: 10k/mês, 1 call/run (batch
de ids) → */2h é trivial. Desvia do default "4h" do CLAUDE.md por causa do limite do free-tier.

Os jobs pegam o pool vivo via `get_pool()` no disparo (pool aberto no lifespan antes do
`scheduler.start()`). `coalesce/max_instances=1` evitam empilhar; com a idempotência dos
workers, re-disparos convergem.
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
        # 1x/dia útil após o fechamento (free-tier BRAPI: 1.000 req/mês, 1 ativo/req).
        CronTrigger(
            day_of_week="mon-fri", hour=19, minute=0, timezone="America/Sao_Paulo"
        ),
        id="price_b3",
        name="price_b3",
    )
    scheduler.add_job(
        _job_price_crypto,
        CronTrigger(hour="*/2", timezone="America/Sao_Paulo"),
        id="price_crypto",
        name="price_crypto",
    )
    return scheduler
