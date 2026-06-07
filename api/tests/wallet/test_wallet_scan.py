"""run_wallet_scan scaffold — agregação fail-soft por fetcher (m4 STORY-04-01)."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from engines.market.fetchers.wallets.binance import BinanceFetcher
from engines.market.fetchers.wallets.etherscan import EtherscanFetcher
from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher
from engines.market.fetchers.wallets.liquid import LiquidFetcher
from engines.market.fetchers.wallets.solana import SolanaFetcher
from workers.wallet_workers import (
    _default_fetchers,
    resolve_owner_id,
    run_wallet_scan,
)


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
async def test_scan_empty_list_is_noop(pool: Any, wallet_user: dict) -> None:
    # lista vazia explícita (NÃO os defaults reais — evita rede no teste)
    uid = wallet_user["user_id"]
    assert await run_wallet_scan(pool, uid, fetchers=[]) == {}


def test_default_fetchers_are_the_five() -> None:
    # o caminho default liga os 5 fetchers reais (sem chamar .fetch() — sem rede)
    types = [type(f) for f in _default_fetchers()]
    assert types == [
        EtherscanFetcher,
        HyperliquidFetcher,
        SolanaFetcher,
        LiquidFetcher,
        BinanceFetcher,
    ]


@pytest.mark.asyncio
async def test_resolve_owner_id_returns_a_user(pool: Any, wallet_user: dict) -> None:
    uid = await resolve_owner_id(pool)
    assert uid is not None and isinstance(uid, str)
