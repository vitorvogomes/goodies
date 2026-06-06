"""upsert_wallet_position — snapshot idempotente (m4 STORY-04-01)."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from engines.wallet import service


@pytest.mark.asyncio
async def test_upsert_inserts_then_updates_in_place(
    pool: Any, wallet_user: dict
) -> None:
    uid = wallet_user["user_id"]
    async with pool.acquire() as conn:
        await service.upsert_wallet_position(
            conn,
            uid,
            WalletBalance("ethereum", "0xabc", "ETH", 1.5, "etherscan"),
        )
        first = await conn.fetchrow(
            "SELECT quantity, scanned_at FROM wallet_positions "
            "WHERE user_id = $1 AND asset_symbol = 'ETH'",
            uid,
        )
        # re-scan com nova quantidade → atualiza em lugar (sem duplicar)
        await service.upsert_wallet_position(
            conn,
            uid,
            WalletBalance("ethereum", "0xabc", "ETH", 2.25, "etherscan"),
        )
        rows = await conn.fetch(
            "SELECT quantity, scanned_at FROM wallet_positions WHERE user_id = $1",
            uid,
        )
    assert len(rows) == 1
    assert float(rows[0]["quantity"]) == 2.25
    assert rows[0]["scanned_at"] >= first["scanned_at"]


@pytest.mark.asyncio
async def test_distinct_assets_coexist(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    async with pool.acquire() as conn:
        await service.upsert_wallet_position(
            conn, uid, WalletBalance("ethereum", "0xabc", "ETH", 1.0, "etherscan")
        )
        await service.upsert_wallet_position(
            conn, uid, WalletBalance("arbitrum", "0xabc", "ARB", 50.0, "etherscan")
        )
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid
        )
    assert n == 2
