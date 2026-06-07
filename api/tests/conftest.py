"""Fixtures compartilhadas — banco de teste isolado + migrations + pool asyncpg.

Os testes rodam num banco DEDICADO (`goodies_test`), NUNCA no `goodies` real.
O DSN é forçado via env ANTES de importar config/db (pydantic-settings lê
DATABASE_URL na 1ª import; env var tem precedência sobre o .env). O banco de
teste é criado on-the-fly e migrado uma vez por sessão.
"""

import asyncio
import os
from pathlib import Path

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://goodies:goodies@localhost:5432/goodies_test"
)
os.environ["DATABASE_URL"] = TEST_DSN

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from db.connection import close_pool, get_pool, init_pool  # noqa: E402

_API_DIR = Path(__file__).resolve().parents[1]
# Banco de manutenção (sempre existe) p/ emitir o CREATE DATABASE goodies_test.
_MAINTENANCE_DSN = TEST_DSN.rsplit("/", 1)[0] + "/goodies"


async def _create_test_db() -> None:
    conn = await asyncpg.connect(_MAINTENANCE_DSN)
    try:
        await conn.execute("CREATE DATABASE goodies_test")
    except asyncpg.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db() -> None:
    asyncio.run(_create_test_db())


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(_ensure_test_db: None) -> None:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "db" / "migrations"))
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def pool():
    await init_pool(TEST_DSN)
    yield get_pool()
    await close_pool()


@pytest.fixture(autouse=True)
def _fresh_price_cache():
    """Reseta o singleton `_cache` do Market Engine a cada teste.

    O cliente `redis.asyncio` liga-se ao event loop em que é usado pela 1ª vez. Com loop
    por-teste (pytest-asyncio), o singleton criado no import ficaria preso a um loop já
    fechado e o `mget` falharia ('Event loop is closed') a partir do 2º teste que o usa
    (exposto quando a valoração de wallet/DeFi passou a ler pelo cache). Em prod o loop é
    único → no-op. Recriar é lazy (sem conexão até o 1º comando).
    """
    from engines.market import service as market_service
    from engines.market.cache import PriceCache

    market_service._cache = PriceCache()
    yield
