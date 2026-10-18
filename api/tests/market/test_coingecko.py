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
async def test_pendle_and_defi_aliases_map_to_coingecko_ids() -> None:
    # usa o mapa REAL de config (PENDLE + aliases DeFi do m4)
    from config import settings

    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "pendle": {"brl": 20.0, "usd": 4.0},
                "hylo-leveraged-sol": {"brl": 1500.0, "usd": 280.0},
                "hylo-usd": {"brl": 5.5, "usd": 1.0},
            },
        )
    )
    fetcher = CoinGeckoFetcher(api_key="k", ids_map=settings.coingecko_ids, sleep=_no_sleep)
    out = await fetcher.fetch(["PENDLE", "xSOL", "hyUSD-2609", "sHYUSD-2609", "YT-xSOL-2609"])
    assert out["PENDLE"].price_brl == 20.0
    assert out["xSOL"].price_usd == 280.0  # casa por símbolo.upper() → XSOL
    # hyUSD-2609 e sHYUSD-2609 mapeiam ao MESMO id (hylo-usd) → ambos cotados
    assert out["hyUSD-2609"].price_brl == 5.5
    assert out["sHYUSD-2609"].price_brl == 5.5
    # YT-xSOL-2609 não tem alias → ignorado (fica sem preço, decisão do m4)
    assert "YT-xSOL-2609" not in out


@pytest.mark.asyncio
@respx.mock
async def test_defi_alias_ignores_maturity_suffix() -> None:
    # rolagem de vencimento: uma NOVA maturidade (hyUSD-2703) ainda deve casar hylo-usd
    from config import settings

    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(200, json={"hylo-usd": {"brl": 5.5, "usd": 1.0}})
    )
    fetcher = CoinGeckoFetcher(api_key="k", ids_map=settings.coingecko_ids, sleep=_no_sleep)
    out = await fetcher.fetch(["hyUSD-2703", "sHYUSD-2811"])
    assert out["hyUSD-2703"].price_brl == 5.5
    assert out["sHYUSD-2811"].price_brl == 5.5


@pytest.mark.asyncio
@respx.mock
async def test_unknown_symbol_skipped() -> None:
    # DOGE não está no mapa -> nem é requisitado; sem ids -> sem chamada
    route = respx.get(url__startswith=_URL).mock(return_value=httpx.Response(200, json={}))
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
