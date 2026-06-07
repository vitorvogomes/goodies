"""Integração m4 (STORY-04-12) — dirige as CLASSES REAIS dos fetchers.

`run_wallet_scan` com os 5 fetchers reais (não fakes), respx mockando TODOS os explorers/
exchange → grava `wallet_positions`; explorer fora → sem linhas, nunca levanta (5xx);
reconciliação/posições via ASGI. Sem rede.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.binance import BinanceFetcher
from engines.market.fetchers.wallets.etherscan import EtherscanFetcher
from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher
from engines.market.fetchers.wallets.liquid import LiquidFetcher
from engines.market.fetchers.wallets.solana import SolanaFetcher
from workers.wallet_workers import run_wallet_scan

_SOL_RPC = "https://rpc.test/sol"
_LBTC = "lbtc-asset-id-test"
_TS = 1_700_000_000.0


async def _no_sleep(_d: float) -> None: ...


def _real_fetchers() -> list[Any]:
    return [
        EtherscanFetcher(api_key="k", address="0xWALLET", sleep=_no_sleep),
        HyperliquidFetcher(address="0xWALLET", sleep=_no_sleep),
        SolanaFetcher(address="SOLADDR", rpc_url=_SOL_RPC, sleep=_no_sleep),
        LiquidFetcher(
            base_url="https://blockstream.info/liquid/api",
            asset_id=_LBTC,
            address="lq1",
            sleep=_no_sleep,
        ),
        BinanceFetcher(
            api_key="k", api_secret="s", symbols=("BTC",), sleep=_no_sleep, clock=lambda: _TS
        ),
    ]


def _mock_all_ok() -> None:
    def eth(request: httpx.Request) -> httpx.Response:
        if request.url.params["action"] == "balance":  # ETH nativo = 1 ETH
            return httpx.Response(200, json={"status": "1", "result": "1000000000000000000"})
        return httpx.Response(  # ARB = 50
            200, json={"status": "1", "result": "50000000000000000000"}
        )

    respx.get(url__startswith="https://api.etherscan.io/v2/api").mock(side_effect=eth)
    respx.post("https://api.hyperliquid.xyz/info").mock(
        return_value=httpx.Response(200, json={"balances": [{"coin": "HYPE", "total": "10"}]})
    )

    def sol(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["method"] == "getBalance":  # 2 SOL
            return httpx.Response(200, json={"result": {"value": 2_000_000_000}})
        return httpx.Response(200, json={"result": {"value": []}})

    respx.post(_SOL_RPC).mock(side_effect=sol)
    respx.get(url__startswith="https://blockstream.info/liquid/api").mock(
        return_value=httpx.Response(200, json=[{"value": 10_000_000, "asset": _LBTC}])  # 0.1
    )
    respx.get(url__startswith="https://api.binance.com/api/v3/time").mock(
        return_value=httpx.Response(200, json={"serverTime": int(_TS * 1000)})
    )
    respx.get(url__startswith="https://api.binance.com/api/v3/account").mock(
        return_value=httpx.Response(
            200, json={"balances": [{"asset": "BTC", "free": "0.5", "locked": "0"}]}
        )
    )
    respx.get(url__startswith="https://api.binance.com/sapi/v1/simple-earn").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )


@pytest.mark.asyncio
@respx.mock
async def test_scan_persists_all_chains(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    _mock_all_ok()
    await run_wallet_scan(pool, uid, fetchers=_real_fetchers())
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chain, asset_symbol, quantity FROM wallet_positions WHERE user_id = $1",
            uid,
        )
    got = {(r["chain"], r["asset_symbol"]): float(r["quantity"]) for r in rows}
    assert got[("ethereum", "ETH")] == pytest.approx(1.0)
    assert got[("arbitrum", "ARB")] == pytest.approx(50.0)
    assert got[("hyperliquid", "HYPE")] == pytest.approx(10.0)
    assert got[("solana", "SOL")] == pytest.approx(2.0)
    assert got[("liquid", "L-BTC")] == pytest.approx(0.1)
    assert got[("binance", "BTC")] == pytest.approx(0.5)


@pytest.mark.asyncio
@respx.mock
async def test_all_explorers_down_no_rows_no_raise(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    respx.route().mock(return_value=httpx.Response(503))  # catch-all: tudo fora
    # não deve levantar (fail-soft de ponta a ponta)
    await run_wallet_scan(pool, uid, fetchers=_real_fetchers())
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid
        )
    assert n == 0


@pytest.mark.asyncio
@respx.mock
async def test_positions_and_reconciliation_via_asgi(
    api: httpx.AsyncClient, pool: Any, wallet_user: dict
) -> None:
    uid = wallet_user["user_id"]
    _mock_all_ok()
    await run_wallet_scan(pool, uid, fetchers=_real_fetchers())
    pos = await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])
    assert pos.status_code == 200
    assert len(pos.json()) == 6  # 6 posições escaneadas
    rec = await api.get("/api/v1/wallets/reconciliation", headers=wallet_user["headers"])
    assert rec.status_code == 200
    by = {r["asset_symbol"]: r for r in rec.json()}
    # sem ops registradas → delta = quantidade escaneada
    assert by["ETH"]["delta"] == pytest.approx(1.0)
    assert by["ETH"]["registered_quantity"] == pytest.approx(0.0)
