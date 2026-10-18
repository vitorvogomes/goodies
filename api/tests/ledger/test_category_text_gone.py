"""Story 10.6 — revisão 0045: o texto de categoria da v1 sai.

`transactions.category`, `fixed_costs.category` e `categories.match_patterns` não existem mais; a
categoria é só o `category_id` (custo fixo também passa a exigi-lo) e o INSERT sem `category_id`
cai em "a classificar" pelo sinal.
"""

from __future__ import annotations

import uuid
from datetime import date

import asyncpg
import pytest


async def _column(conn: asyncpg.Connection, table: str, column: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = $2)",
            table,
            column,
        )
    )


@pytest.mark.asyncio
async def test_text_columns_are_gone(pool) -> None:
    async with pool.acquire() as conn:
        assert not await _column(conn, "transactions", "category")
        assert not await _column(conn, "fixed_costs", "category")
        assert not await _column(conn, "categories", "match_patterns")
        assert await _column(conn, "transactions", "category_id")
        nullable = await conn.fetchval(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'fixed_costs' AND column_name = 'category_id'"
        )
    assert nullable == "NO"


@pytest.mark.asyncio
async def test_insert_without_category_falls_to_pending_by_sign(pool) -> None:
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
            f"t-{uuid.uuid4().hex[:8]}",
        )
        try:
            keys = {}
            for amount in (10, -10):
                keys[amount] = await conn.fetchval(
                    "WITH t AS (INSERT INTO transactions (account_id, date, amount) "
                    "VALUES ($1, $2, $3) RETURNING category_id) "
                    "SELECT c.key FROM t JOIN categories c ON c.id = t.category_id",
                    acc,
                    date(2099, 9, 1),
                    amount,
                )
        finally:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
    assert keys == {10: "sistema:entrada_a_classificar", -10: "sistema:saida_a_classificar"}


@pytest.mark.asyncio
async def test_fixed_cost_requires_category(pool) -> None:
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.NotNullViolationError):
            await conn.execute(
                "INSERT INTO fixed_costs (name, amount, due_day) VALUES ('sem categoria', 10, 5)"
            )
