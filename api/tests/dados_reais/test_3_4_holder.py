"""Story 3.4 — revisão 0024 sobre a base real: titular das contas Nubank (PF e MEI) e a tabela de
saldo informado; nada mais muda; idempotente."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from tests.dados_reais.conftest import restore_dados
from tests.dados_reais.test_2_6_reclassificacoes import _downgrade
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _holders(dsn: str) -> dict[str, str | None]:
    conn = await asyncpg.connect(dsn)
    try:
        return dict(await conn.fetch("SELECT name, holder FROM accounts ORDER BY name"))
    finally:
        await conn.close()


async def test_titular_das_contas_nubank() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0024_holder_balances")
        holders = await _holders(dsn)
        assert holders == {"Nubank_CNPJ": "mei", "Nubank_CPF": "pf"}
        conn = await asyncpg.connect(dsn)
        try:
            assert await conn.fetchval("SELECT count(*) FROM account_balances") == 0
        finally:
            await conn.close()
        await asyncio.to_thread(_downgrade, dsn, "0023_assets")
        await asyncio.to_thread(alembic_upgrade, dsn, "0024_holder_balances")
        assert await _holders(dsn) == holders
    finally:
        await restore_dados()
