"""Story 2.2 — revisões 0016 (user_id no ledger) e 0017 (lotes legacy) sobre a base real.

restaura → mede → `alembic upgrade 0017` → mede. Invariantes (AD-16 + ADR-016): contagens iguais,
zero
órfãs, toda linha com `user_id` e `source`, toda linha de arquivo com lote, poupança de cada mês
igual
à do baseline fixado. Idempotência: downgrade + upgrade dá os mesmos lotes e as mesmas atribuições.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import asyncpg
import pytest

from scripts.ops.baseline import pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

REV = "0017_import_batches"


def _savings_baseline() -> dict[str, str | None]:
    path = pinned_baseline()
    if path is None or not path.is_file():
        require_or_skip("baseline fixado não encontrado")
        raise AssertionError("inalcançável")
    data: dict[str, str | None] = json.loads(path.read_text())["savings_rate"]
    return data


async def _savings(conn: asyncpg.Connection) -> dict[str, str | None]:
    rows = await conn.fetch(
        "SELECT to_char(month, 'YYYY-MM') AS m, savings_rate FROM monthly_summary ORDER BY 1"
    )
    return {
        r["m"]: None if r["savings_rate"] is None else str(round(r["savings_rate"], 6))
        for r in rows
    }


async def _snapshot(conn: asyncpg.Connection) -> dict[str, object]:
    return {
        "transactions": await conn.fetchval("SELECT count(*) FROM transactions"),
        "asset_operations": await conn.fetchval("SELECT count(*) FROM asset_operations"),
        "accounts": await conn.fetchval("SELECT count(*) FROM accounts"),
        "categories": await conn.fetchval("SELECT count(*) FROM categories"),
        "fixed_costs": await conn.fetchval("SELECT count(*) FROM fixed_costs"),
        "soma_tx": await conn.fetchval("SELECT COALESCE(sum(amount), 0) FROM transactions"),
    }


async def _upgrade(dsn: str, rev: str) -> None:
    await asyncio.to_thread(alembic_upgrade, dsn, rev)


async def test_proveniencia_do_historico() -> None:
    dsn = await restore_dados()
    try:
        conn = await asyncpg.connect(dsn)
        try:
            before = await _snapshot(conn)
            tesouro_manual = await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE external_id LIKE 'tesouro-sale-return:%'"
            )
        finally:
            await conn.close()

        await _upgrade(dsn, REV)

        conn = await asyncpg.connect(dsn)
        try:
            assert await _snapshot(conn) == before  # nada criado nem apagado
            for table in ("accounts", "transactions", "categories", "fixed_costs"):
                owner_less = await conn.fetchval(
                    f"SELECT count(*) FROM {table} WHERE user_id IS NULL"
                )
                assert owner_less == 0, table
            for table in ("transactions", "asset_operations"):
                assert (
                    await conn.fetchval(f"SELECT count(*) FROM {table} WHERE source IS NULL") == 0
                )
                sem_lote = await conn.fetchval(
                    f"SELECT count(*) FROM {table} WHERE batch_id IS NULL "
                    "AND source NOT IN ('manual', 'hermes', 'derived')"
                )
                assert sem_lote == 0, table
            by_src = dict(await conn.fetch("SELECT source, count(*) FROM transactions GROUP BY 1"))
            assert by_src.get("manual", 0) == tesouro_manual
            assert sum(by_src.values()) == before["transactions"]
            # um lote legacy por (fonte, conta) e por (fonte, corretora), com o período das linhas
            legacy = await conn.fetch(
                "SELECT f.source, f.account_id, f.broker, f.period_start, f.period_end "
                "FROM import_batches b JOIN import_batch_files f ON f.batch_id = b.id "
                "WHERE b.status = 'legacy'"
            )
            tx_groups = await conn.fetchval(
                "SELECT count(DISTINCT (source, account_id)) FROM transactions "
                "WHERE batch_id IS NOT NULL"
            )
            op_groups = await conn.fetchval(
                "SELECT count(DISTINCT (source, broker)) FROM asset_operations "
                "WHERE batch_id IS NOT NULL"
            )
            assert len(legacy) == tx_groups + op_groups
            span = await conn.fetchrow(
                "SELECT min(date) mi, max(date) ma FROM transactions WHERE batch_id IS NOT NULL"
            )
            assert min(r["period_start"] for r in legacy) <= span["mi"]
            assert max(r["period_end"] for r in legacy) >= span["ma"]
            # poupança de cada mês = baseline (ADR-016; jun/2026 incluído)
            assert await _savings(conn) == _savings_baseline()
            ids_1 = sorted(str(r["id"]) for r in await conn.fetch("SELECT id FROM import_batches"))
        finally:
            await conn.close()

        # idempotência: volta para 0016 e reaplica — mesmos lotes, mesmas contagens
        await asyncio.to_thread(_downgrade, dsn, "0016_ledger_user_id")
        await _upgrade(dsn, REV)
        conn = await asyncpg.connect(dsn)
        try:
            ids_2 = sorted(str(r["id"]) for r in await conn.fetch("SELECT id FROM import_batches"))
            assert ids_2 == ids_1
            assert await _snapshot(conn) == before
            assert isinstance(before["soma_tx"], Decimal)
        finally:
            await conn.close()
    finally:
        await restore_dados()


def _downgrade(dsn: str, rev: str) -> None:
    import os
    import subprocess

    from workers.dbops import API_DIR

    subprocess.run(
        ["alembic", "downgrade", rev],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": dsn},
        check=True,
    )
