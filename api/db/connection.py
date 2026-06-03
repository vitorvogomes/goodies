"""Pool asyncpg do Postgres — STORY-00-03.

Sem ORM (conventions.md): queries SQL explícitas via asyncpg. O pool é global,
inicializado no startup do FastAPI (init_pool) e fechado no shutdown (close_pool).
"""

from collections.abc import AsyncGenerator

import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Cria o pool (idempotente). min 2, max 10 conexões (story 00-03)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn or settings.database_url,
            min_size=2,
            max_size=10,
        )
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("pool asyncpg não inicializado — chame init_pool() no startup")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_postgres() -> tuple[str, str]:
    """Check plugável do health (api/health.py). Fail-soft: nunca levanta exceção."""
    try:
        async with get_pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
        return ("postgres", "connected")
    except Exception:
        return ("postgres", "disconnected")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency do FastAPI: cede uma conexão do pool."""
    async with get_pool().acquire() as conn:
        yield conn
