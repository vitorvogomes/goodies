"""Fetcher CoinGecko (cripto) — STORY-03-03. Mockado com respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.coingecko import CoinGeckoFetcher

_URL = "https://api.coingecko.com/api/v3/simple/price"
_IDS = {"BTC": "bitcoin", "ETH": "ethereum"}


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> CoinGeckoFetcher:
    return CoinGeckoFetcher(api_key="k", ids_map=_IDS, sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_maps_symbol_to_id_and_fills_brl_usd() -> None:
    route = respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "bitcoin": {"brl": 350000.0, "usd": 65000.0},
                "ethereum": {"brl": 18000.0, "usd": 3400.0},
            },
        )
    )
    out = await _fetcher().fetch(["BTC", "ETH"])
    assert out["BTC"].price_brl == 350000.0
    assert out["BTC"].price_usd == 65000.0
    assert out["BTC"].source == "coingecko"
    assert out["ETH"].price_usd == 3400.0
    # ids resolvidos pelo mapa de config
    assert "ids=" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_unknown_symbol_skipped() -> None:
    # DOGE não está no mapa -> nem é requisitado; sem ids -> sem chamada
    route = respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(200, json={})
    )
    out = await _fetcher().fetch(["DOGE"])
    assert out == {}
    assert route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_429_then_succeeds() -> None:
    respx.get(url__startswith=_URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"bitcoin": {"brl": 360000.0, "usd": 66000.0}}),
        ]
    )
    out = await _fetcher().fetch(["BTC"])
    assert out["BTC"].price_brl == 360000.0


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty() -> None:
    respx.get(url__startswith=_URL).mock(return_value=httpx.Response(500))
    out = await _fetcher().fetch(["BTC"])
    assert out == {}
