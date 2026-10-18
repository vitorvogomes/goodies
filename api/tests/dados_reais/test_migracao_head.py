"""Story 1.2 (review e1) — o `dados_reais` exercita a migração pendente: restaura → mede →
`alembic upgrade head` → mede. É a parte genérica dos invariantes da AD-16 (contagens e zero órfãs);
cada revisão de dado acrescenta os seus (55,48%, deltas esperados) num teste próprio.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade, current_revision, head_revision

pytestmark = pytest.mark.asyncio(loop_scope="session")

_COUNTS = {
    "transactions": "SELECT count(*) FROM transactions",
    "asset_operations": "SELECT count(*) FROM asset_operations",
    "transacoes_sem_conta": (
        "SELECT count(*) FROM transactions t LEFT JOIN accounts a ON a.id = t.account_id "
        "WHERE a.id IS NULL"
    ),
}


async def _measure(dsn: str) -> dict[str, int]:
    conn = await asyncpg.connect(dsn)
    try:
        return {k: int(await conn.fetchval(sql)) for k, sql in _COUNTS.items()}
    finally:
        await conn.close()


async def test_upgrade_head_preserva_contagens_e_sem_orfas() -> None:
    dsn = await restore_dados()
    try:
        before = await _measure(dsn)
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        assert await current_revision(dsn) == head_revision()
        after = await _measure(dsn)
        assert after == before
        assert after["transacoes_sem_conta"] == 0
    finally:
        await restore_dados()  # devolve a base fixada para os demais testes da sessão
