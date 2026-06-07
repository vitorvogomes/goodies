"""BitcoinFetcher — BTC mainchain (Trust), client dedicado (ADR-005). Mock respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.bitcoin import BitcoinFetcher

_BTC_BASE = "https://blockstream.info/api"


async def _no_sleep(_d: float) -> None: ...


def _fetcher(base: str = _BTC_BASE) -> BitcoinFetcher:
    return BitcoinFetcher(base_url=base, address="bc1qaddr", sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_confirmed_balance_funded_minus_spent() -> None:
    route = respx.get(url__startswith=_BTC_BASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {"funded_txo_sum": 150_000_000, "spent_txo_sum": 50_000_000},
                "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0},
            },
        )
    )
    out = await _fetcher().fetch()
    assert len(out) == 1
    assert out[0].asset_symbol == "BTC"
    assert out[0].chain == "bitcoin"
    assert out[0].source == "bitcoin"
    assert out[0].quantity == pytest.approx(1.0)  # (150M - 50M) sats / 1e8
    # ADR-005: mainchain usa /api (NÃO /liquid/api)
    path = route.calls.last.request.url.path
    assert path == "/api/address/bc1qaddr"
    assert "/liquid/api" not in path


@pytest.mark.asyncio
@respx.mock
async def test_zero_balance_returns_empty() -> None:
    respx.get(url__startswith=_BTC_BASE).mock(
        return_value=httpx.Response(
            200, json={"chain_stats": {"funded_txo_sum": 70_000, "spent_txo_sum": 70_000}}
        )
    )
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty() -> None:
    respx.get(url__startswith=_BTC_BASE).mock(return_value=httpx.Response(502))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await BitcoinFetcher(address="", sleep=_no_sleep).fetch() == []
