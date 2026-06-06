"""Fetcher BRAPI.dev (B3) — ações/ETFs/FIIs. STORY-03-02.

`GET https://brapi.dev/api/quote/{ticker}?token=...` — UMA requisição por ticker (o
plano grátis do BRAPI permite no máximo 1 ativo por requisição: batch retorna 400
`QUOTES_PER_REQUEST_EXCEEDED`). Remove o sufixo `F` de fracionário (PETR4F → PETR4).
Retry 3x com backoff 1s/2s/4s por ticker (`with_retry`). Fail-soft (CLAUDE.md): API
fora ou ticker sem cotação → aquele símbolo é omitido; nunca levanta para o worker.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from config import settings

from .base import PriceQuote, with_retry

_BASE_URL = "https://brapi.dev/api/quote"
_SOURCE = "brapi"


def _strip_fractional(ticker: str) -> str:
    """PETR4F → PETR4 (mesma regra de `b3_import.parse_produto`, inline p/ não acoplar)."""
    t = ticker.strip()
    if len(t) > 1 and t.endswith("F") and t[-2].isdigit():
        return t[:-1]
    return t


class BrapiFetcher:
    """Cota B3 via BRAPI. `client`/`sleep` injetáveis para teste."""

    def __init__(
        self,
        token: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._token = token if token is not None else settings.brapi_token
        self._client = client
        self._sleep = sleep

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        if not symbols:
            return {}
        # símbolo original -> símbolo BRAPI (sem F); um PETR4F e um PETR4 colapsam.
        norm = {s: _strip_fractional(s) for s in symbols}
        client = self._client or httpx.AsyncClient()
        by_symbol: dict[str, float] = {}
        try:
            for ticker in sorted(set(norm.values())):

                async def _one(t: str = ticker) -> Any:
                    return await self._request(client, t)

                try:
                    data = await with_retry(
                        _one,
                        attempts=4,  # 1 tentativa + 3 retries (backoff 1s/2s/4s)
                        sleep=self._sleep,
                    )
                except Exception:
                    continue  # fail-soft por ticker: um erro não derruba os demais
                for item in data.get("results", []) if isinstance(data, dict) else []:
                    sym = item.get("symbol")
                    price = item.get("regularMarketPrice")
                    if sym and price is not None:
                        by_symbol[str(sym)] = float(price)
        finally:
            if self._client is None:
                await client.aclose()

        out: dict[str, PriceQuote] = {}
        for original, brapi_sym in norm.items():
            price = by_symbol.get(brapi_sym)
            if price is not None:
                out[original] = PriceQuote(price_brl=price, price_usd=None, source=_SOURCE)
        return out

    async def _request(self, client: httpx.AsyncClient, ticker: str) -> Any:
        params = {"token": self._token} if self._token else {}
        resp = await client.get(f"{_BASE_URL}/{ticker}", params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
