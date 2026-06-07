"""BinanceFetcher — spot + earn assinado (HMAC). STORY-04-05. Mock respx."""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.binance import BinanceFetcher

_BASE = "https://api.binance.com"
_SECRET = "test-secret"
_TS = 1_700_000_000.0  # clock fixo → assinatura determinística


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> BinanceFetcher:
    return BinanceFetcher(
        api_key="test-key",
        api_secret=_SECRET,
        symbols=("BTC", "ETH", "SOL"),
        sleep=_no_sleep,
        clock=lambda: _TS,
    )


def _route(path: str, payload: dict) -> None:
    respx.get(url__startswith=f"{_BASE}{path}").mock(
        return_value=httpx.Response(200, json=payload)
    )


def _mock_time(server_ms: int | None = None) -> None:
    """Mocka /api/v3/time. Default = relógio local (_TS) → offset 0 (determinístico)."""
    ms = server_ms if server_ms is not None else int(_TS * 1000)
    respx.get(url__startswith=f"{_BASE}/api/v3/time").mock(
        return_value=httpx.Response(200, json={"serverTime": ms})
    )


@pytest.mark.asyncio
@respx.mock
async def test_aggregates_spot_and_earn() -> None:
    _mock_time()
    _route("/api/v3/account", {"balances": [
        {"asset": "BTC", "free": "0.5", "locked": "0.1"},
        {"asset": "ETH", "free": "2.0", "locked": "0"},
        {"asset": "DUST", "free": "100", "locked": "0"},  # fora de symbols → dropado
    ]})
    _route("/sapi/v1/simple-earn/flexible/position", {"rows": [
        {"asset": "BTC", "totalAmount": "0.4"},  # soma ao spot do BTC
    ]})
    _route("/sapi/v1/simple-earn/locked/position", {"rows": [
        {"asset": "SOL", "amount": "30"},
    ]})
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert out["BTC"].quantity == pytest.approx(1.0)  # 0.5 + 0.1 + 0.4
    assert out["ETH"].quantity == pytest.approx(2.0)
    assert out["SOL"].quantity == pytest.approx(30.0)
    assert "DUST" not in out
    assert out["BTC"].chain == "binance" and out["BTC"].source == "binance"


@pytest.mark.asyncio
@respx.mock
async def test_signs_request_and_sends_api_key() -> None:
    _mock_time()
    route = _signed_account_route()
    await _fetcher().fetch()
    req = route.calls.last.request
    assert req.headers["X-MBX-APIKEY"] == "test-key"
    # assinatura = HMAC_SHA256(secret, "timestamp=...&recvWindow=...")
    expected_query = urlencode({"timestamp": int(_TS * 1000), "recvWindow": 5000})
    expected_sig = hmac.new(
        _SECRET.encode(), expected_query.encode(), hashlib.sha256
    ).hexdigest()
    assert req.url.params["signature"] == expected_sig


@pytest.mark.asyncio
@respx.mock
async def test_fail_soft_per_endpoint() -> None:
    _mock_time()
    respx.get(url__startswith=f"{_BASE}/api/v3/account").mock(
        return_value=httpx.Response(500)  # spot fora
    )
    _route(
        "/sapi/v1/simple-earn/flexible/position",
        {"rows": [{"asset": "ETH", "totalAmount": "1.5"}]},
    )
    _route("/sapi/v1/simple-earn/locked/position", {"rows": []})
    out = {b.asset_symbol: b for b in await _fetcher().fetch()}
    assert "BTC" not in out  # spot caiu
    assert out["ETH"].quantity == pytest.approx(1.5)  # earn sobreviveu


@pytest.mark.asyncio
@respx.mock
async def test_all_endpoints_down_returns_empty() -> None:
    respx.get(url__startswith=_BASE).mock(return_value=httpx.Response(503))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_applies_server_time_offset() -> None:
    """Clock-skew: o timestamp enviado = relógio local + (serverTime - local)."""
    local_ms = int(_TS * 1000)
    server_ms = local_ms + 5000  # servidor 5s à frente
    _mock_time(server_ms)
    route = _signed_account_route()
    await _fetcher().fetch()
    params = route.calls.last.request.url.params
    assert int(params["timestamp"]) == server_ms  # offset aplicado
    # a assinatura confere sobre o timestamp corrigido
    expected_query = urlencode({"timestamp": server_ms, "recvWindow": 5000})
    expected_sig = hmac.new(
        _SECRET.encode(), expected_query.encode(), hashlib.sha256
    ).hexdigest()
    assert params["signature"] == expected_sig


@pytest.mark.asyncio
@respx.mock
async def test_time_endpoint_failure_falls_back_to_local_clock() -> None:
    respx.get(url__startswith=f"{_BASE}/api/v3/time").mock(
        return_value=httpx.Response(500)  # /time fora → offset 0
    )
    route = _signed_account_route()
    await _fetcher().fetch()
    assert int(route.calls.last.request.url.params["timestamp"]) == int(_TS * 1000)


@pytest.mark.asyncio
async def test_no_credentials_is_noop() -> None:
    assert await BinanceFetcher(api_key="", api_secret="", sleep=_no_sleep).fetch() == []


def _signed_account_route() -> respx.Route:
    payload = {"balances": [{"asset": "BTC", "free": "1", "locked": "0"}]}
    return respx.get(url__startswith=f"{_BASE}/api/v3/account").mock(
        return_value=httpx.Response(200, json=payload)
    )
