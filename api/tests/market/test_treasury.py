"""Fetcher Tesouro Direto (Tesouro Transparente CSV) — STORY-03-04. Mockado com respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.treasury import TreasuryFetcher

_URL = "https://www.tesourotransparente.gov.br"

_HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha"
)
_CSV = "\n".join(
    [
        _HEADER,
        # base ANTIGA (deve ser ignorada em favor da mais recente)
        "Tesouro IPCA+;15/05/2029;04/06/2026;7,00;7,05;3700,00;3700,10;3700,05",
        "Tesouro IPCA+;15/05/2029;05/06/2026;7,10;7,15;3735,90;3735,96;3735,96",
        "Tesouro Prefixado;01/01/2032;05/06/2026;13,0;13,1;471,30;471,38;471,35",
        "Tesouro Selic;01/03/2028;05/06/2026;0,0;0,04;19140,00;19141,21;19141,00",
        # variante COM JUROS SEMESTRAIS — NÃO deve casar com "Tesouro IPCA+ 2029"
        "Tesouro IPCA+ com Juros Semestrais;15/05/2029;05/06/2026;7,2;7,3;0;9999,99;9999,99",
    ]
)


async def _no_sleep(_d: float) -> None: ...


def _fetcher() -> TreasuryFetcher:
    return TreasuryFetcher(sleep=_no_sleep)


def _mock_csv(status: int = 200) -> None:
    respx.get(url__startswith=_URL).mock(
        return_value=httpx.Response(status, content=_CSV.encode("latin-1"))
    )


@pytest.mark.asyncio
@respx.mock
async def test_matches_and_picks_latest_base() -> None:
    _mock_csv()
    out = await _fetcher().fetch(["Tesouro IPCA+ 2029", "Tesouro Selic 2028"])
    assert out["Tesouro IPCA+ 2029"].price_brl == 3735.96  # base 05/06, não 04/06
    assert out["Tesouro IPCA+ 2029"].source == "tesouro"
    assert out["Tesouro Selic 2028"].price_brl == 19141.21


@pytest.mark.asyncio
@respx.mock
async def test_exact_type_match_ignores_juros_semestrais() -> None:
    _mock_csv()
    out = await _fetcher().fetch(["Tesouro IPCA+ 2029"])
    # casa o principal (3735,96), NÃO a variante "com Juros Semestrais" (9999,99)
    assert out["Tesouro IPCA+ 2029"].price_brl == 3735.96


@pytest.mark.asyncio
@respx.mock
async def test_prefixado() -> None:
    _mock_csv()
    out = await _fetcher().fetch(["Tesouro Prefixado 2032"])
    assert out["Tesouro Prefixado 2032"].price_brl == 471.38


@pytest.mark.asyncio
@respx.mock
async def test_no_match_omitted() -> None:
    _mock_csv()
    out = await _fetcher().fetch(["Tesouro IPCA+ 2099"])
    assert out == {}


@pytest.mark.asyncio
async def test_non_treasury_symbol_skipped() -> None:
    # ticker que não casa o padrão "Tesouro <tipo> <ano>" nem dispara download
    out = await _fetcher().fetch(["PETR4"])
    assert out == {}


@pytest.mark.asyncio
@respx.mock
async def test_source_down_returns_empty() -> None:
    _mock_csv(status=503)
    out = await _fetcher().fetch(["Tesouro IPCA+ 2029"])
    assert out == {}
