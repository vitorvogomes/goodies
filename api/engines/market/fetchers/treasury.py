"""Fetcher Tesouro Direto — STORY-03-04. API pública (sem chave).

`GET .../service/api/treasury/bond/list` devolve a lista de títulos com nome e preço
unitário de resgate. Matching FLEXÍVEL por nome (normaliza acento/caixa/espaços), pois
o ticker do portfólio ("Tesouro IPCA+ 2040") pode diferir levemente da grafia da API.
Fail-soft: API fora / sem casamento → símbolo omitido. TTL de cache (6h) é do worker.
"""
from __future__ import annotations

import asyncio
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from .base import PriceQuote, with_retry

_BASE_URL = (
    "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/"
    "service/api/treasury/bond/list"
)
_SOURCE = "tesouro"

# A API pública do Tesouro bloqueia clientes sem cabeçalhos de navegador (403).
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://www.tesourodireto.com.br/titulos/precos-e-taxas.htm",
}


def _norm(name: str) -> str:
    """Normaliza p/ casamento: sem acento, minúsculo, espaços colapsados."""
    nfkd = unicodedata.normalize("NFKD", name)
    no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(no_accent.lower().split())


def _unit_price(bond: dict[str, Any]) -> float | None:
    """Preço unitário de resgate (valor atual da posição); cai p/ o de investimento."""
    for key in ("untrRedVal", "untrInvstmtVal"):
        val = bond.get(key)
        if val is not None:
            return float(val)
    return None


class TreasuryFetcher:
    """Cota Tesouro Direto. `client`/`sleep` injetáveis para teste."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        if not symbols:
            return {}
        client = self._client or httpx.AsyncClient()
        try:
            data = await with_retry(
                lambda: self._request(client), attempts=4, sleep=self._sleep
            )
        except Exception:
            return {}  # fail-soft: API indisponível → nada
        finally:
            if self._client is None:
                await client.aclose()

        # nome normalizado -> preço unitário
        by_name: dict[str, float] = {}
        bonds = (
            data.get("response", {}).get("TrsrBdTradgList", [])
            if isinstance(data, dict)
            else []
        )
        for item in bonds:
            bond = item.get("TrsrBd", {}) if isinstance(item, dict) else {}
            name = bond.get("nm")
            price = _unit_price(bond)
            if name and price is not None:
                by_name[_norm(str(name))] = price

        out: dict[str, PriceQuote] = {}
        for sym in symbols:
            price = self._match(sym, by_name)
            if price is not None:
                out[sym] = PriceQuote(price_brl=price, price_usd=None, source=_SOURCE)
        return out

    @staticmethod
    def _match(symbol: str, by_name: dict[str, float]) -> float | None:
        key = _norm(symbol)
        if key in by_name:
            return by_name[key]
        # casamento flexível: nome da API contém o ticker (ou vice-versa)
        for name, price in by_name.items():
            if key in name or name in key:
                return price
        return None

    async def _request(self, client: httpx.AsyncClient) -> Any:
        resp = await client.get(_BASE_URL, headers=_HEADERS, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
