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
async def test_scans_multiple_addresses() -> None:
    """Phantom + Neobankless num só fetcher → posições distintas por wallet_address (m4)."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        addr = body["params"][0]
        if body["method"] == "getBalance":
            val = 1_000_000_000 if addr == "ADDR1" else 2_000_000_000
            return httpx.Response(200, json={"result": {"value": val}})
        accts = [_token_account(_USDC, 50.0)] if addr == "ADDR2" else []
        return httpx.Response(200, json={"result": {"value": accts}})

    respx.post(_RPC).mock(side_effect=handler)
    out = await SolanaFetcher(
        addresses=["ADDR1", "ADDR2"], sleep=_no_sleep, rpc_url=_RPC
    ).fetch()
    by = {(b.wallet_address, b.asset_symbol): b for b in out}
    assert by[("ADDR1", "SOL")].quantity == 1.0
    assert by[("ADDR2", "SOL")].quantity == 2.0
    assert by[("ADDR2", "USDC")].quantity == 50.0
    assert all(b.source == "solana" and b.chain == "solana" for b in out)


@pytest.mark.asyncio
@respx.mock
async def test_default_scans_phantom_and_neobankless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem args → escaneia as 2 wallets Solana das settings (Phantom + Neobankless)."""
    from config import settings

    monkeypatch.setattr(settings, "wallet_phantom_sol_address", "PHANTOM")
    monkeypatch.setattr(settings, "wallet_neobankless_address", "NEO")
    monkeypatch.setattr(settings, "solana_rpc_url", _RPC)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "getBalance":
            val = 1_000_000_000 if body["params"][0] == "PHANTOM" else 3_000_000_000
            return httpx.Response(200, json={"result": {"value": val}})
        return httpx.Response(200, json={"result": {"value": []}})

    respx.post(_RPC).mock(side_effect=handler)
    out = await SolanaFetcher(sleep=_no_sleep).fetch()
    assert {b.wallet_address for b in out} == {"PHANTOM", "NEO"}


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
