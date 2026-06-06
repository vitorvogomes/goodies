"""Fetcher Tesouro Direto — STORY-03-04. Mockado com respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.treasury import TreasuryFetcher

_URL = "https://www.tesourodireto.com.br/json"

_PAYLOAD = {
    "response": {
        "TrsrBdTradgList": [
            {"TrsrBd": {"nm": "Tesouro IPCA+ 2040", "untrRedVal": 1771.82}},
            {"TrsrBd": {"nm": "Tesouro Selic 2029", "untrRedVal": 16500.50}},
            {"TrsrBd": {"nm": "Tesouro Prefixado 2032", "untrRedVal": 700.18}},
        ]
    }
}


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> TreasuryFetcher:
    return TreasuryFetcher(sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_matches_full_name() -> None:
    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    out = await _fetcher().fetch(["Tesouro IPCA+ 2040", "Tesouro Selic 2029"])
    assert out["Tesouro IPCA+ 2040"].price_brl == 1771.82
    assert out["Tesouro IPCA+ 2040"].source == "tesouro"
    assert out["Tesouro Selic 2029"].price_brl == 16500.50


@pytest.mark.asyncio
@respx.mock
async def test_flexible_match_ignores_accent_and_case() -> None:
    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    # grafia ligeiramente diferente (sem casar exato byte-a-byte)
    out = await _fetcher().fetch(["tesouro prefixado 2032"])
    assert out["tesouro prefixado 2032"].price_brl == 700.18


@pytest.mark.asyncio
@respx.mock
async def test_no_match_omitted() -> None:
    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    out = await _fetcher().fetch(["Tesouro IPCA+ 2099"])
    assert out == {}


@pytest.mark.asyncio
@respx.mock
async def test_api_down_returns_empty() -> None:
    respx.get(url__startswith=_URL).mock(return_value=httpx.Response(503))
    out = await _fetcher().fetch(["Tesouro IPCA+ 2040"])
    assert out == {}
