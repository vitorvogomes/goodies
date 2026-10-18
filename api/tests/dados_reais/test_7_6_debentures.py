"""Story 7.6 na base real: a revisão 0040 cadastra a debênture Flash sobre o ativo que existia,
LIGA as integralizações do seed antigo às transações do trilho (mesma data e valor, sem reinserir,
`protected`) e as registra como contribuições confirmadas; o aplicado Flash não muda (o do baseline
da Story 1.3) e rodar de novo não muda nada."""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import date

import asyncpg
import pytest

from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")
FLASH = "Flash-Debênture"


async def _state(conn: asyncpg.Connection) -> tuple[int, int, int, int]:
    ops = await conn.fetchval(
        "SELECT count(*) FROM asset_operations WHERE asset_symbol = $1", FLASH
    )
    linked = await conn.fetchval(
        "SELECT count(*) FROM asset_operations WHERE asset_symbol = $1 "
        "AND transaction_id IS NOT NULL AND protected",
        FLASH,
    )
    confirmed = await conn.fetchval(
        "SELECT count(*) FROM debenture_contributions WHERE status = 'confirmed'"
    )
    debentures = await conn.fetchval("SELECT count(*) FROM debentures")
    return ops, linked, confirmed, debentures


async def test_debentures_ligadas_sem_reinserir() -> None:
    import main  # noqa: F401

    base = load_pinned_baseline()
    if base is None:
        require_or_skip("baseline fixado ausente")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0039_transaction_asset")
        conn = await asyncpg.connect(dsn)
        try:
            before = await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE asset_symbol = $1", FLASH
            )
        finally:
            await conn.close()
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            ops, linked, confirmed, debentures = await _state(conn)
            assert ops == before and ops > 0  # nada reinserido
            assert linked == ops == confirmed and debentures == 1
            deb = await conn.fetchrow(
                "SELECT d.issuer, d.monthly_factor, a.valuation FROM debentures d "
                "JOIN assets a ON a.id = d.asset_id"
            )
            assert (deb["issuer"], str(deb["monthly_factor"]), deb["valuation"]) == (
                "Flash",
                "1.780000",
                "taxa",
            )
            migration = importlib.import_module("db.migrations.versions.0040_debentures")
            for statement in migration._UPGRADE:  # idempotente
                await conn.execute(statement)
            assert await _state(conn) == (ops, linked, confirmed, debentures)
            got = json.loads(
                json.dumps(
                    await compute_baseline(conn, date.fromisoformat(base["evaluation_date"]))
                )
            )
        finally:
            await conn.close()
        assert got["aplicado"].get(FLASH) == base["aplicado"].get(FLASH)
        assert got["net"].get(FLASH) == base["net"].get(FLASH)
    finally:
        await restore_dados()
