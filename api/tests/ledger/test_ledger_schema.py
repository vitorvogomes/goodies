"""Schema do Ledger (STORY-01-01).

Cobre as tabelas accounts/transactions/fixed_costs, a coluna aditiva
transactions.external_id (dedup de import Nubank por FITID) e a view
monthly_summary (taxa de poupança).

A view agrega por mês sobre TODA a tabela transactions; por isso cada teste usa
um mês improvável (2099) e filtra por ele, limpando os dados ao fim.
"""

import uuid
from datetime import date

import asyncpg
import pytest


async def _make_account(conn: asyncpg.Connection) -> uuid.UUID:
    return await conn.fetchval(
        "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id",
        f"test-{uuid.uuid4().hex[:8]}",
        "bank",
    )


async def test_monthly_summary_savings_rate(pool):
    # receita 10000, despesa 4500 -> taxa de poupança 55% (fórmula da STORY-01-05).
    async with pool.acquire() as conn:
        acc = await _make_account(conn)
        await conn.executemany(
            "INSERT INTO transactions (account_id, date, amount, category) VALUES ($1, $2, $3, $4)",
            [
                (acc, date(2099, 1, 5), 10000, "income"),
                (acc, date(2099, 1, 20), -4500, "food"),
            ],
        )
        row = await conn.fetchrow(
            "SELECT total_income, total_expense, net_cashflow, savings_rate "
            "FROM monthly_summary WHERE month = date_trunc('month', $1::date)",
            date(2099, 1, 1),
        )
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)

    assert row is not None
    assert float(row["total_income"]) == 10000.0
    assert float(row["total_expense"]) == 4500.0
    assert float(row["net_cashflow"]) == 5500.0
    assert abs(float(row["savings_rate"]) - 55.0) < 0.01


async def test_transactions_external_id_unique_allows_nulls(pool):
    async with pool.acquire() as conn:
        acc = await _make_account(conn)
        fitid = uuid.uuid4().hex
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category, external_id) "
            "VALUES ($1, $2, $3, $4, $5)",
            acc,
            date(2099, 2, 1),
            -10,
            "x",
            fitid,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, external_id) "
                "VALUES ($1, $2, $3, $4, $5)",
                acc,
                date(2099, 2, 2),
                -20,
                "y",
                fitid,
            )
        # external_id NULL pode repetir (índice único parcial WHERE external_id IS NOT NULL).
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category) VALUES ($1, $2, $3, $4)",
            acc,
            date(2099, 2, 3),
            -30,
            "z",
        )
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category) VALUES ($1, $2, $3, $4)",
            acc,
            date(2099, 2, 4),
            -40,
            "w",
        )
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)


async def test_transactions_notes_column(pool):
    async with pool.acquire() as conn:
        acc = await _make_account(conn)
        tx = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, notes) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            acc,
            date(2099, 3, 1),
            -10,
            "outros",
            "comprei no mercado",
        )
        notes = await conn.fetchval("SELECT notes FROM transactions WHERE id = $1", tx)
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
    assert notes == "comprei no mercado"


async def test_accounts_account_number_unique_allows_nulls(pool):
    num = f"NUM-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        a1 = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, $2, $3) RETURNING id",
            "A1",
            "bank",
            num,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO accounts (name, type, account_number) VALUES ($1, $2, $3)",
                "A2",
                "bank",
                num,
            )
        # account_number NULL pode repetir (índice único parcial)
        b1 = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "B1", "bank"
        )
        b2 = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id", "B2", "bank"
        )
        await conn.execute("DELETE FROM accounts WHERE id = ANY($1::uuid[])", [a1, b1, b2])


async def test_fixed_costs_roundtrip(pool):
    async with pool.acquire() as conn:
        fc = await conn.fetchval(
            "INSERT INTO fixed_costs (name, amount, due_day, category) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            "Aluguel",
            1500,
            5,
            "moradia",
        )
        row = await conn.fetchrow(
            "SELECT name, amount, due_day, category, is_active FROM fixed_costs WHERE id = $1",
            fc,
        )
        await conn.execute("DELETE FROM fixed_costs WHERE id = $1", fc)

    assert row["name"] == "Aluguel"
    assert int(row["due_day"]) == 5
    assert row["is_active"] is True
