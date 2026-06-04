"""Aplicação FastAPI do Goodies — STORY-00-02 (+ 00-03/00-04 health, 00-05 auth).

Instância base + CORS + health check com checks plugáveis de componentes
(Postgres em 00-03, Redis em 00-04). Auth JWT (00-05) no router /api/v1/auth.
O pool asyncpg é aberto no startup (lifespan) e fechado no shutdown.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from config import settings
from db.connection import check_postgres, close_pool, init_pool
from engines.ledger.router import router as ledger_router
from engines.market.cache import check_redis
from health import collect_component_status, register_component_check

# Checks incluídos no /api/v1/health (registrados no import do módulo).
register_component_check(check_postgres)
register_component_check(check_redis)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Goodies API", version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ledger_router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
        **await collect_component_status(),
    }
