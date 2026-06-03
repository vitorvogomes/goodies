"""Fixtures dos testes de db — STORY-00-03.

Aplica as migrations Alembic no Postgres de teste (Docker-local) antes da sessão,
deixando os testes self-contained (não dependem de setup manual / igual ao CI).
"""

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config

from db.connection import close_pool, get_pool, init_pool

_API_DIR = Path(__file__).resolve().parents[2]
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
