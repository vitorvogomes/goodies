"""SolanaFetcher — SOL nativo + SPL via JSON-RPC. STORY-04-03. Mock respx."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.solana import SolanaFetcher

_RPC = "https://rpc.test/solana"
_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> SolanaFetcher:
    return SolanaFetcher(address="SOLADDR", sleep=_no_sleep, rpc_url=_RPC)


def _token_account(mint: str, ui_amount: float) -> dict:
    return {
        "account": {
            "data": {"parsed": {"info": {"mint": mint, "tokenAmount": {"uiAmount": ui_amount}}}}
        }
    }


@pytest.mark.asyncio
@respx.mock
async def test_sol_native_and_spl() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "getBalance":  # 1.5 SOL em lamports
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                             "result": {"value": 1500000000}})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                         "result": {"value": [_token_account(_USDC, 25.0)]}})

    respx.post(_RPC).mock(side_effect=handler)
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert out["SOL"].quantity == 1.5
    assert out["SOL"].chain == "solana"
    assert out["SOL"].source == "solana"
    assert out["USDC"].quantity == 25.0


@pytest.mark.asyncio
@respx.mock
async def test_unknown_mint_omitted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "getBalance":
            return httpx.Response(200, json={"result": {"value": 0}})
        return httpx.Response(
            200, json={"result": {"value": [_token_account("UNKNOWNmint", 999.0)]}}
        )

    respx.post(_RPC).mock(side_effect=handler)
    assert await _fetcher().fetch() == []  # SOL 0 omitido + mint desconhecido omitido


@pytest.mark.asyncio
@respx.mock
async def test_spl_survives_when_balance_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "getBalance":  # erro no SOL nativo
            return httpx.Response(200, json={"error": {"code": -32000, "message": "boom"}})
        return httpx.Response(
            200, json={"result": {"value": [_token_account(_USDC, 10.0)]}}
        )

    respx.post(_RPC).mock(side_effect=handler)
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert "SOL" not in out
    assert out["USDC"].quantity == 10.0


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty() -> None:
    respx.post(_RPC).mock(return_value=httpx.Response(500))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_is_noop() -> None:
    assert await SolanaFetcher(address="", sleep=_no_sleep, rpc_url=_RPC).fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_uses_settings_rpc_url_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "solana_rpc_url", "https://custom.rpc/sol")
    route = respx.post("https://custom.rpc/sol").mock(
        return_value=httpx.Response(200, json={"result": {"value": 1_000_000_000}})
    )
    # sem rpc_url → usa settings.solana_rpc_url (apontar p/ Helius/QuickNode = só env)
    await SolanaFetcher(address="SOLADDR", sleep=_no_sleep).fetch()
    assert route.called
