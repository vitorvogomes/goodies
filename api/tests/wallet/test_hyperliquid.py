"""HyperliquidFetcher — HYPE spot (Info API) + HyperEVM nativo. STORY-04-02 / m4. respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher

_URL = "https://api.hyperliquid.xyz/info"
_EVM = "https://rpc.test/hyperevm"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> HyperliquidFetcher:
    return HyperliquidFetcher(address="0xWALLET", sleep=_no_sleep, hyperevm_rpc_url=_EVM)


def _evm_balance(wei: int) -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": hex(wei)})


@pytest.mark.asyncio
@respx.mock
async def test_parses_hype_total() -> None:
    info = respx.post(_URL).mock(
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
    respx.post(_EVM).mock(return_value=_evm_balance(0))  # sem HYPE na HyperEVM
    out = await _fetcher().fetch()
    assert len(out) == 1
    assert out[0].asset_symbol == "HYPE"
    assert out[0].quantity == 42.5
    assert out[0].chain == "hyperliquid"
    assert out[0].source == "hyperliquid"
    # corpo da requisição spot = spotClearinghouseState p/ o endereço
    body = info.calls.last.request.content.decode()
    assert "spotClearinghouseState" in body and "0xWALLET" in body


@pytest.mark.asyncio
@respx.mock
async def test_includes_hyperevm_native_hype() -> None:
    # HYPE existe em DOIS lugares: spot L1 (0.00979) + HyperEVM nativo (0.3108)
    respx.post(_URL).mock(
        return_value=httpx.Response(
            200, json={"balances": [{"coin": "HYPE", "total": "0.00979"}]}
        )
    )
    respx.post(_EVM).mock(return_value=_evm_balance(310_800_000_000_000_000))  # 0.3108 HYPE
    out = {(b.chain, b.asset_symbol): b for b in await _fetcher().fetch()}
    assert out[("hyperliquid", "HYPE")].quantity == pytest.approx(0.00979)
    assert out[("hyperevm", "HYPE")].quantity == pytest.approx(0.3108)
    assert out[("hyperevm", "HYPE")].source == "hyperliquid"


@pytest.mark.asyncio
@respx.mock
async def test_hyperevm_failure_keeps_spot() -> None:
    # HyperEVM fora (500) não derruba o saldo spot (fail-soft por fonte)
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "HYPE", "total": "1.0"}]})
    )
    respx.post(_EVM).mock(return_value=httpx.Response(500))
    out = await _fetcher().fetch()
    assert {(b.chain, b.quantity) for b in out} == {("hyperliquid", 1.0)}


@pytest.mark.asyncio
@respx.mock
async def test_spot_failure_keeps_hyperevm() -> None:
    # spot fora não impede a HyperEVM (e vice-versa)
    respx.post(_URL).mock(return_value=httpx.Response(500))
    respx.post(_EVM).mock(return_value=_evm_balance(500_000_000_000_000_000))  # 0.5 HYPE
    out = await _fetcher().fetch()
    assert len(out) == 1
    assert out[0].chain == "hyperevm"
    assert out[0].quantity == pytest.approx(0.5)


@pytest.mark.asyncio
@respx.mock
async def test_hype_absent_returns_empty() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "USDC", "total": "5"}]})
    )
    respx.post(_EVM).mock(return_value=_evm_balance(0))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_zero_total_omitted() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "HYPE", "total": "0"}]})
    )
    respx.post(_EVM).mock(return_value=_evm_balance(0))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_error_is_fail_soft() -> None:
    respx.post(_URL).mock(return_value=httpx.Response(500))
    respx.post(_EVM).mock(return_value=httpx.Response(500))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await HyperliquidFetcher(address="", sleep=_no_sleep).fetch() == []
