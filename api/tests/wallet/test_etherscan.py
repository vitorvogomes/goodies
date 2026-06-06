"""EtherscanFetcher (V2 multichain) — ETH + ARB. STORY-04-02. Mock respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.etherscan import EtherscanFetcher

_BASE = "https://api.etherscan.io/v2/api"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> EtherscanFetcher:
    return EtherscanFetcher(api_key="k", address="0xWALLET", sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_native_and_token_balance_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        action = request.url.params["action"]
        if action == "balance":  # ETH nativo: 1.5 ETH em wei
            return httpx.Response(
                200, json={"status": "1", "message": "OK", "result": "1500000000000000000"}
            )
        # ARB ERC-20: 100 ARB (18 casas)
        return httpx.Response(
            200, json={"status": "1", "message": "OK", "result": "100000000000000000000"}
        )

    respx.get(url__startswith=_BASE).mock(side_effect=handler)
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert out["ETH"].quantity == 1.5
    assert out["ETH"].chain == "ethereum"
    assert out["ETH"].source == "etherscan"
    assert out["ARB"].quantity == 100.0
    assert out["ARB"].chain == "arbitrum"


@pytest.mark.asyncio
@respx.mock
async def test_passes_chainid_per_spec() -> None:
    route = respx.get(url__startswith=_BASE).mock(
        return_value=httpx.Response(200, json={"status": "1", "result": "0"})
    )
    await _fetcher().fetch()
    chainids = {c.request.url.params["chainid"] for c in route.calls}
    assert chainids == {"1", "42161"}  # mainnet + arbitrum


@pytest.mark.asyncio
@respx.mock
async def test_zero_balance_is_omitted() -> None:
    respx.get(url__startswith=_BASE).mock(
        return_value=httpx.Response(200, json={"status": "1", "result": "0"})
    )
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_status_zero_is_fail_soft_per_spec() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["chainid"] == "1":  # ETH falha (status 0)
            return httpx.Response(200, json={"status": "0", "message": "NOTOK", "result": "x"})
        return httpx.Response(  # ARB ok
            200, json={"status": "1", "result": "5000000000000000000"}
        )

    respx.get(url__startswith=_BASE).mock(side_effect=handler)
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert "ETH" not in out  # spec que falhou é omitida
    assert out["ARB"].quantity == 5.0  # a outra sobrevive


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty_no_raise() -> None:
    respx.get(url__startswith=_BASE).mock(return_value=httpx.Response(500))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await EtherscanFetcher(api_key="k", address="", sleep=_no_sleep).fetch() == []
