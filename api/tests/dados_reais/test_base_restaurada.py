"""Story 1.2 — a base dos testes de dado real sai do backup fixado com as mesmas contagens."""

from __future__ import annotations

import asyncpg
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_base_restaurada_tem_historico(dados_dsn: str) -> None:
    conn = await asyncpg.connect(dados_dsn)
    try:
        tx = await conn.fetchval("SELECT count(*) FROM transactions")
        ops = await conn.fetchval("SELECT count(*) FROM asset_operations")
        first = await conn.fetchval("SELECT min(date) FROM transactions")
    finally:
        await conn.close()
    assert tx > 1000 and ops > 0
    assert str(first) == "2024-06-01"
