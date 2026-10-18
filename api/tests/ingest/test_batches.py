"""Story 2.2 — engine ingest: lote aplicado com arquivos, leitura pela dona."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.ingest import service
from engines.ingest.models import BatchFileIn


@pytest.mark.asyncio
async def test_record_and_list_applied_batch(pool: Any) -> None:
    async with pool.acquire() as conn:
        bid = await service.record_applied_batch(
            conn,
            [
                BatchFileIn(
                    source="b3_movimentacao",
                    broker="B3-movimentacao",
                    file_name="mov.xlsx",
                    period_start=date(2026, 6, 1),
                    period_end=date(2026, 10, 16),
                )
            ],
        )
        batches = await service.list_batches(conn, limit=50)
        status = await conn.fetchval("SELECT status FROM import_batches WHERE id = $1", bid)
        await conn.execute("DELETE FROM import_batches WHERE id = $1", bid)
    assert status == "applied"
    mine = next(b for b in batches if b.id == bid)
    assert mine.applied_at is not None
    assert [(f.source, f.broker, f.period_end) for f in mine.files] == [
        ("b3_movimentacao", "B3-movimentacao", date(2026, 10, 16))
    ]


@pytest.mark.asyncio
async def test_batch_without_files_is_refused(pool: Any) -> None:
    async with pool.acquire() as conn:
        with pytest.raises(ValueError):
            await service.record_applied_batch(conn, [])


@pytest.mark.asyncio
async def test_file_row_without_batch_is_refused_by_the_schema(pool: Any) -> None:
    import asyncpg

    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ('sem lote', 'bank') RETURNING id"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, source) "
                "VALUES ($1, '2099-01-01', -1, 'outros', 'nubank_ofx')",
                acc,
            )
        # lançamento à mão: sem lote, origem manual (padrão)
        src = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category) "
            "VALUES ($1, '2099-01-01', -1, 'outros') RETURNING source",
            acc,
        )
        owner = await conn.fetchval("SELECT user_id FROM accounts WHERE id = $1", acc)
        first = await conn.fetchval("SELECT id FROM users ORDER BY created_at, id LIMIT 1")
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
    assert src == "manual"
    assert owner == first  # user_id preenchido com o dono único
