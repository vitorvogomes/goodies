"""RED tests: asset_operations and portfolio_targets schema validation."""

import uuid
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any

import asyncpg
import pytest


@pytest.fixture
async def _cleanup_test_data(pool: Any) -> AsyncGenerator[None, None]:
    """Cleanup test users after each test."""
    yield
    # Clean up dependent tables first to respect FKs
    await pool.execute(
        "DELETE FROM portfolio_targets WHERE user_id IN "
        "(SELECT id FROM users WHERE email LIKE 'test_%_%@test.com')"
    )
    await pool.execute(
        "DELETE FROM users WHERE email LIKE 'test_%_%@test.com'"
    )


@pytest.mark.asyncio
async def test_asset_operations_table_exists(pool: Any) -> None:
    """asset_operations table must exist."""
    result = await pool.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'asset_operations'
        """
    )
    assert result == 1


@pytest.mark.asyncio
async def test_asset_operations_columns(pool: Any) -> None:
    """asset_operations must have all required columns."""
    columns = await pool.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'asset_operations'
        ORDER BY column_name
        """
    )
    column_names = {col["column_name"] for col in columns}
    required = {
        "id",
        "user_id",
        "broker",
        "asset_symbol",
        "asset_category",
        "tipo",
        "quantidade",
        "valor_unitario",
        "data_operacao",
        "notes",
        "external_id",
        "created_at",
    }
    assert required <= column_names


@pytest.mark.asyncio
async def test_asset_operations_tipo_constraint(
    pool: Any, _cleanup_test_data: Any
) -> None:
    """tipo column must enforce CHECK constraint."""
    email = f"test_tipo_{uuid.uuid4().hex[:8]}@test.com"
    user_id = await pool.fetchval(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
        email,
        "hash",
    )

    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await pool.execute(
            """
            INSERT INTO asset_operations
            (user_id, broker, asset_symbol, asset_category, tipo, quantidade,
             valor_unitario, data_operacao)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            user_id,
            "TestBroker",
            "TEST",
            "TestCategory",
            "invalid_tipo",
            1.0,
            100.0,
            date(2026, 1, 1),
        )


@pytest.mark.asyncio
async def test_asset_operations_quantidade_positive(
    pool: Any, _cleanup_test_data: Any
) -> None:
    """quantidade column must enforce positive CHECK constraint."""
    email = f"test_qty_{uuid.uuid4().hex[:8]}@test.com"
    user_id = await pool.fetchval(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
        email,
        "hash",
    )

    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await pool.execute(
            """
            INSERT INTO asset_operations
            (user_id, broker, asset_symbol, asset_category, tipo, quantidade,
             valor_unitario, data_operacao)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            user_id,
            "TestBroker",
            "TEST",
            "TestCategory",
            "compra",
            -1.0,
            100.0,
            date(2026, 1, 1),
        )


@pytest.mark.asyncio
async def test_asset_prices_table_exists(pool: Any) -> None:
    """asset_prices table must exist (0008 — manual prices for m2)."""
    result = await pool.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'asset_prices'
        """
    )
    assert result == 1


@pytest.mark.asyncio
async def test_asset_prices_columns(pool: Any) -> None:
    """asset_prices must have all required columns."""
    columns = await pool.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'asset_prices'
        ORDER BY column_name
        """
    )
    column_names = {col["column_name"] for col in columns}
    required = {
        "ticker",
        "price_brl",
        "price_usd",
        "source",
        "is_manual",
        "fetched_at",
    }
    assert required <= column_names


@pytest.mark.asyncio
async def test_asset_prices_ticker_pk_upsert(pool: Any) -> None:
    """asset_prices ticker is PK — second insert same ticker must conflict."""
    await pool.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source) VALUES ($1, $2, $3)",
        "TEST_PK",
        10.0,
        "manual",
    )
    try:
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await pool.execute(
                "INSERT INTO asset_prices (ticker, price_brl, source) "
                "VALUES ($1, $2, $3)",
                "TEST_PK",
                20.0,
                "manual",
            )
    finally:
        await pool.execute("DELETE FROM asset_prices WHERE ticker = $1", "TEST_PK")


@pytest.mark.asyncio
async def test_portfolio_targets_table_exists(pool: Any) -> None:
    """portfolio_targets table must exist."""
    result = await pool.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'portfolio_targets'
        """
    )
    assert result == 1


@pytest.mark.asyncio
async def test_portfolio_targets_unique_category(
    pool: Any, _cleanup_test_data: Any
) -> None:
    """portfolio_targets must enforce UNIQUE(user_id, category)."""
    email = f"test_unique_{uuid.uuid4().hex[:8]}@test.com"
    user_id = await pool.fetchval(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
        email,
        "hash",
    )

    # Insert first target
    await pool.execute(
        """
        INSERT INTO portfolio_targets (user_id, category, target_pct)
        VALUES ($1, $2, $3)
        """,
        user_id,
        "Ações Nacionais",
        10.0,
    )

    # Insert duplicate should fail
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await pool.execute(
            """
            INSERT INTO portfolio_targets (user_id, category, target_pct)
            VALUES ($1, $2, $3)
            """,
            user_id,
            "Ações Nacionais",
            15.0,
        )
