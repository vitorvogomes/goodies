"""Story 8.2 na base real: a revisão 0043 passa `portfolio_targets` para `planning` (banda, piso,
vigência) sem mudar as metas — mesmo % por classe antes e depois, vigentes desde jul/2024, banda
de 5 p.p. e piso 0 (P22) —, o seed só entra na tabela vazia e a tela v1 de alocação lê as metas
por `planning`."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import asyncpg
import pytest

from engines.common.owner import get_owner_id
from engines.planning import targets
from engines.portfolio import service as portfolio_service
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_mesmas_metas_por_classe() -> None:
    import main  # noqa: F401

    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0042_goals")
        conn = await asyncpg.connect(dsn)
        try:
            before = {
                r["class"]: Decimal(r["target_pct"])
                for r in await conn.fetch("SELECT class, target_pct FROM portfolio_targets")
            }
        finally:
            await conn.close()
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            owner = await get_owner_id(conn)
            after = await targets.class_targets(conn)
            count = await conn.fetchval("SELECT count(*) FROM portfolio_targets")
            allocation = await portfolio_service.calculate_allocation(conn, owner)
        finally:
            await conn.close()
    finally:
        await restore_dados()
    assert before and {c: Decimal(r["target_pct"]) for c, r in after.items()} == before
    assert sum(before.values()) == Decimal(100)
    assert {(str(r["valid_from"]), r["band_pp"], r["floor"]) for r in after.values()} == {
        ("2024-07-01", Decimal("5.00"), Decimal("0.00"))
    }
    assert count == len(before)  # o seed da revisão só entra na tabela vazia
    metas = {c["category"]: c["pct_meta"] for c in allocation["categories"]}
    assert {k: Decimal(str(v)) for k, v in metas.items() if v is not None} == {
        targets.CATEGORY_BY_CLASS[c]: v for c, v in before.items()
    }
