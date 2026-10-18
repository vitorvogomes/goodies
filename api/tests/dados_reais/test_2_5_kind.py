"""Story 2.5 — invariante de `kind` (na suíte e no /gate): toda transação tem o `kind` do grupo da
sua subcategoria, na base real migrada até o head."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_kind_igual_ao_do_grupo() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            divergent = await conn.fetch(
                "SELECT t.id, t.kind, g.kind AS group_kind FROM transactions t "
                "JOIN categories c ON c.id = t.category_id "
                "JOIN category_groups g ON g.id = c.group_id WHERE t.kind <> g.kind"
            )
            sem_categoria = await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE category_id IS NULL"
            )
        finally:
            await conn.close()
    finally:
        await restore_dados()
    assert [dict(r) for r in divergent] == []
    assert sem_categoria == 0
