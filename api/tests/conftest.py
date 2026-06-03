"""Fixtures compartilhadas — aplica migrations + pool asyncpg (Docker-local).

Top-level: serve testes de db, auth e integração. Migrations rodam uma vez por
sessão (idempotente), deixando os testes self-contained / iguais ao CI.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config

from db.connection import close_pool, get_pool, init_pool

_API_DIR = Path(__file__).resolve().parents[1]
DEV_DSN = "postgresql://goodies:goodies@localhost:5432/goodies"


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "db" / "migrations"))
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def pool():
    await init_pool(DEV_DSN)
    yield get_pool()
    await close_pool()
