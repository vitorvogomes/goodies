"""EtherscanFetcher (V2 multichain) — ETH + ARB + ETH/PENDLE (Arbitrum). STORY-04-02 / m4."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.etherscan import EtherscanFetcher

_BASE = "https://api.etherscan.io/v2/api"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> EtherscanFetcher:
    return EtherscanFetcher(api_key="k", address="0xWALLET", sleep=_no_sleep)


_ARB_CONTRACT = "0x912CE59144191C1204E64559FE8253a0e49E6548".lower()
_PENDLE_CONTRACT = "0x0c880f6761f1af8d9aa9c466984b80dab9a8c9e8"


@pytest.mark.asyncio
@respx.mock
async def test_native_and_token_balance_normalized() -> None:
    # 4 specs: ETH/eth, ARB/arb, ETH/arb (nativo), PENDLE/arb (ERC-20). m4.
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        if p["action"] == "balance":  # ETH nativo: 1.5 na mainnet, 0.5 na Arbitrum
            wei = "1500000000000000000" if p["chainid"] == "1" else "500000000000000000"
            return httpx.Response(200, json={"status": "1", "message": "OK", "result": wei})
        # ERC-20: distingue ARB (100) de PENDLE (42) pelo contractaddress
        contract = p["contractaddress"].lower()
        raw = "100000000000000000000" if contract == _ARB_CONTRACT else "42000000000000000000"
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": raw})

    respx.get(url__startswith=_BASE).mock(side_effect=handler)
    out = {(b.chain, b.asset_symbol): b for b in await _fetcher().fetch()}
    assert out[("ethereum", "ETH")].quantity == 1.5
    assert out[("ethereum", "ETH")].source == "etherscan"
    assert out[("arbitrum", "ETH")].quantity == 0.5  # ETH nativo na Arbitrum (m4)
    assert out[("arbitrum", "ARB")].quantity == 100.0
    assert out[("arbitrum", "PENDLE")].quantity == 42.0  # PENDLE ERC-20 na Arbitrum (m4)


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
    out = {(b.chain, b.asset_symbol): b for b in await _fetcher().fetch()}
    assert ("ethereum", "ETH") not in out  # spec da mainnet (chainid 1) falhou → omitida
    assert out[("arbitrum", "ARB")].quantity == 5.0  # specs da Arbitrum sobrevivem
    assert out[("arbitrum", "ETH")].quantity == 5.0


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty_no_raise() -> None:
    respx.get(url__startswith=_BASE).mock(return_value=httpx.Response(500))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await EtherscanFetcher(api_key="k", address="", sleep=_no_sleep).fetch() == []
