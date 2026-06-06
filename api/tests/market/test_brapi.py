"""Fetcher BRAPI (B3) — STORY-03-02. APIs mockadas com respx (sem rede)."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.brapi import BrapiFetcher

_QUOTE = "https://brapi.dev/api/quote/"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> BrapiFetcher:
    return BrapiFetcher(token="test-token", sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_strips_f_suffix_and_parses_price() -> None:
    route = respx.get(url__startswith=_QUOTE).mock(
        return_value=httpx.Response(
            200, json={"results": [{"symbol": "PETR4", "regularMarketPrice": 28.5}]}
        )
    )
    out = await _fetcher().fetch(["PETR4F"])
    assert out["PETR4F"].price_brl == 28.5
    assert out["PETR4F"].price_usd is None
    assert out["PETR4F"].source == "brapi"
    # pediu PETR4 (sem o sufixo F de fracionário)
    path = route.calls.last.request.url.path
    assert path.endswith("/PETR4")


@pytest.mark.asyncio
@respx.mock
async def test_one_request_per_ticker() -> None:
    # plano grátis: 1 ativo por requisição → uma chamada por ticker
    respx.get(url__startswith=f"{_QUOTE}PETR4").mock(
        return_value=httpx.Response(
            200, json={"results": [{"symbol": "PETR4", "regularMarketPrice": 28.5}]}
        )
    )
    respx.get(url__startswith=f"{_QUOTE}BBAS3").mock(
        return_value=httpx.Response(
            200, json={"results": [{"symbol": "BBAS3", "regularMarketPrice": 20.1}]}
        )
    )
    out = await _fetcher().fetch(["PETR4", "BBAS3"])
    assert out["PETR4"].price_brl == 28.5
    assert out["BBAS3"].price_brl == 20.1


@pytest.mark.asyncio
@respx.mock
async def test_one_ticker_fails_others_survive() -> None:
    # fail-soft por ticker: PETR4 cai (500 persistente), BBAS3 cota normalmente
    respx.get(url__startswith=f"{_QUOTE}PETR4").mock(return_value=httpx.Response(500))
    respx.get(url__startswith=f"{_QUOTE}BBAS3").mock(
        return_value=httpx.Response(
            200, json={"results": [{"symbol": "BBAS3", "regularMarketPrice": 20.1}]}
        )
    )
    out = await _fetcher().fetch(["PETR4", "BBAS3"])
    assert "PETR4" not in out
    assert out["BBAS3"].price_brl == 20.1


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_429_then_succeeds() -> None:
    respx.get(url__startswith=_QUOTE).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(
                200, json={"results": [{"symbol": "PETR4", "regularMarketPrice": 30.0}]}
            ),
        ]
    )
    out = await _fetcher().fetch(["PETR4"])
    assert out["PETR4"].price_brl == 30.0


@pytest.mark.asyncio
@respx.mock
async def test_persistent_5xx_returns_empty_no_raise() -> None:
    respx.get(url__startswith=_QUOTE).mock(return_value=httpx.Response(500))
    out = await _fetcher().fetch(["PETR4"])
    assert out == {}  # fail-soft: nunca levanta para o worker


@pytest.mark.asyncio
@respx.mock
async def test_unknown_ticker_omitted() -> None:
    respx.get(url__startswith=_QUOTE).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    out = await _fetcher().fetch(["ZZZZ9"])
    assert out == {}


@pytest.mark.asyncio
async def test_empty_symbols_no_request() -> None:
    out = await _fetcher().fetch([])
    assert out == {}
