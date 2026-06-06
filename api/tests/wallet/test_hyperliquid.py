"""HyperliquidFetcher — HYPE spot via Info API. STORY-04-02. Mock respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher

_URL = "https://api.hyperliquid.xyz/info"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> HyperliquidFetcher:
    return HyperliquidFetcher(address="0xWALLET", sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_parses_hype_total() -> None:
    route = respx.post(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": [
                    {"coin": "USDC", "total": "12.0", "hold": "0"},
                    {"coin": "HYPE", "total": "42.5", "hold": "1.0"},
                ]
            },
        )
    )
    out = await _fetcher().fetch()
    assert len(out) == 1
    assert out[0].asset_symbol == "HYPE"
    assert out[0].quantity == 42.5
    assert out[0].chain == "hyperliquid"
    assert out[0].source == "hyperliquid"
    # corpo da requisição = spotClearinghouseState p/ o endereço
    body = route.calls.last.request.content.decode()
    assert "spotClearinghouseState" in body and "0xWALLET" in body


@pytest.mark.asyncio
@respx.mock
async def test_hype_absent_returns_empty() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "USDC", "total": "5"}]})
    )
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_zero_total_omitted() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "HYPE", "total": "0"}]})
    )
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_error_is_fail_soft() -> None:
    respx.post(_URL).mock(return_value=httpx.Response(500))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await HyperliquidFetcher(address="", sleep=_no_sleep).fetch() == []
