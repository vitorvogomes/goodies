"""Base dos testes `dados_reais` (Story 1.2): `goodies_dados`, restaurado do backup fixado.

Ordem dos testes de migração: restaura → mede → `alembic upgrade <rev>` → mede. A restauração
é feita uma vez por sessão; quem migra a base chama `restore_dados()` de novo antes de medir
o "antes".

Sem backup fixado (ou sem `BACKUP_DIR`), os testes são **pulados com aviso explícito** — nunca dão
verde falso. Com `DADOS_REAIS_REQUIRED=1` (usado por `scripts.ops.migrar` e pelo `/gate`),
pular vira falha.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from tests.conftest import TEST_DSN
from workers.backup import BackupDirError, DbTarget, pinned_dados_backup, restore

DADOS_DSN = DbTarget.from_dsn(TEST_DSN).with_database("goodies_dados").dsn()


def require_or_skip(reason: str) -> None:
    if os.environ.get("DADOS_REAIS_REQUIRED") == "1":
        pytest.fail(f"dados_reais obrigatório e indisponível: {reason}")
    pytest.skip(f"dados_reais PULADO: {reason} — rode `python -m scripts.ops.restore_dados_db`")


def pinned_or_skip() -> Path:
    try:
        source = pinned_dados_backup()
    except BackupDirError as exc:
        require_or_skip(str(exc))
        raise AssertionError("inalcançável") from exc
    if source is None or not source.is_file():
        require_or_skip("backup pré-migração fixado não encontrado em BACKUP_DIR/pre-migracao")
        raise AssertionError("inalcançável")
    return source


async def restore_dados() -> str:
    await restore(pinned_or_skip(), DADOS_DSN)
    return DADOS_DSN


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dados_dsn() -> AsyncIterator[str]:
    yield await restore_dados()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.dados_reais)
