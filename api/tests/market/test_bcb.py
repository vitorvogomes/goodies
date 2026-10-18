"""BcbFetcher — CDI/IPCA via SGS do BCB. STORY-04-07. Mock respx."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from engines.market.fetchers.bcb import BcbFetcher

_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> BcbFetcher:
    return BcbFetcher(sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_parses_cdi_and_ipca() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if ".12/" in request.url.path:  # CDI
            return httpx.Response(200, json=[{"data": "06/06/2026", "valor": "0.053"}])
        return httpx.Response(200, json=[{"data": "01/06/2026", "valor": "0.41"}])  # IPCA

    respx.get(url__startswith=_BASE).mock(side_effect=handler)
    out = {p.series: p for p in await _fetcher().fetch()}
    assert out["CDI"].value == pytest.approx(0.053)
    assert out["CDI"].ref_date == date(2026, 6, 6)
    assert out["CDI"].source == "bcb"
    assert out["IPCA"].value == pytest.approx(0.41)
    assert out["IPCA"].ref_date == date(2026, 6, 1)


@pytest.mark.asyncio
@respx.mock
async def test_one_series_fails_other_survives() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if ".12/" in request.url.path:
            return httpx.Response(500)  # CDI fora
        return httpx.Response(200, json=[{"data": "01/06/2026", "valor": "0.41"}])

    respx.get(url__startswith=_BASE).mock(side_effect=handler)
    out = {p.series for p in await _fetcher().fetch()}
    assert out == {"IPCA"}


@pytest.mark.asyncio
@respx.mock
async def test_all_down_returns_empty() -> None:
    respx.get(url__startswith=_BASE).mock(return_value=httpx.Response(503))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_empty_payload_is_skipped() -> None:
    respx.get(url__startswith=_BASE).mock(return_value=httpx.Response(200, json=[]))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_range_uses_sgs_interval() -> None:
    """Story 7.2: busca por intervalo (`dataInicial`/`dataFinal`) e devolve todos os pontos."""
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        if ".12/" in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {"data": "03/06/2024", "valor": "0.039"},
                    {"data": "04/06/2024", "valor": "0.04"},
                ],
            )
        return httpx.Response(200, json=[{"data": "01/06/2024", "valor": "0.21"}])

    respx.get(url__regex=rf"{_BASE}\.\d+/dados(\?|$)").mock(side_effect=handler)
    out = await _fetcher().fetch_range(date(2024, 6, 1), date(2024, 6, 30))
    assert {(p.series, p.ref_date) for p in out} == {
        ("CDI", date(2024, 6, 3)),
        ("CDI", date(2024, 6, 4)),
        ("IPCA", date(2024, 6, 1)),
    }
    assert all(s["dataInicial"] == "01/06/2024" and s["dataFinal"] == "30/06/2024" for s in seen)
