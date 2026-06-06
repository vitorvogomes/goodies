"""run_wallet_scan scaffold — agregação fail-soft por fetcher (m4 STORY-04-01)."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from workers.wallet_workers import run_wallet_scan


class _FakeFetcher:
    def __init__(self, balances: list[WalletBalance]) -> None:
        self._balances = balances

    async def fetch(self) -> list[WalletBalance]:
        return self._balances


class _BoomFetcher:
    async def fetch(self) -> list[WalletBalance]:
        raise RuntimeError("chain down")


@pytest.mark.asyncio
async def test_scan_writes_positions(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    fake = _FakeFetcher(
        [
            WalletBalance("ethereum", "0xabc", "ETH", 1.0, "etherscan"),
            WalletBalance("arbitrum", "0xabc", "ARB", 100.0, "etherscan"),
        ]
    )
    stats = await run_wallet_scan(pool, uid, fetchers=[fake])
    assert stats["_FakeFetcher"] == {"fetched": 2, "failed": 0}
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid
        )
    assert n == 2


@pytest.mark.asyncio
async def test_scan_idempotent_rerun(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    fake = _FakeFetcher([WalletBalance("solana", "sol1", "SOL", 5.0, "solscan")])
    await run_wallet_scan(pool, uid, fetchers=[fake])
    await run_wallet_scan(pool, uid, fetchers=[fake])
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid
        )
    assert n == 1  # snapshot — não duplica


@pytest.mark.asyncio
async def test_scan_fail_soft_one_fetcher_down(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    ok = _FakeFetcher([WalletBalance("liquid", "lq1", "L-BTC", 0.1, "liquid")])
    stats = await run_wallet_scan(pool, uid, fetchers=[_BoomFetcher(), ok])
    assert stats["_BoomFetcher"] == {"fetched": 0, "failed": 1}
    assert stats["_FakeFetcher"] == {"fetched": 1, "failed": 0}
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid
        )
    assert n == 1  # o fetcher bom grava mesmo com o outro fora


@pytest.mark.asyncio
async def test_scan_no_fetchers_is_noop(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    assert await run_wallet_scan(pool, uid) == {}
