"""Schema de wallet_positions (migration 0010) — m4 STORY-04-01."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_table_exists(pool: Any) -> None:
    result = await pool.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'wallet_positions'"
    )
    assert result == 1


@pytest.mark.asyncio
async def test_columns(pool: Any) -> None:
    rows = await pool.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'wallet_positions'"
    )
    names = {r["column_name"] for r in rows}
    assert {
        "id",
        "user_id",
        "chain",
        "wallet_address",
        "asset_symbol",
        "quantity",
        "source",
        "scanned_at",
        "created_at",
    } <= names


@pytest.mark.asyncio
async def test_unique_per_user_chain_wallet_asset(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    ins = (
        "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
        "quantity, source) VALUES ($1, 'ethereum', '0xabc', 'ETH', $2, 'etherscan')"
    )
    async with pool.acquire() as conn:
        await conn.execute(ins, uid, 1)
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(ins, uid, 2)


@pytest.mark.asyncio
async def test_quantity_non_negative_check(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO wallet_positions (user_id, chain, wallet_address, "
                "asset_symbol, quantity, source) "
                "VALUES ($1, 'ethereum', '0xabc', 'ETH', -1, 'etherscan')",
                uid,
            )


@pytest.mark.asyncio
async def test_rls_enabled(pool: Any) -> None:
    enabled = await pool.fetchval(
        "SELECT relrowsecurity FROM pg_class WHERE relname = 'wallet_positions'"
    )
    assert enabled is True
