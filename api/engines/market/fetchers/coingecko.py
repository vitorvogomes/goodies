"""Fetcher CoinGecko (cripto) — STORY-03-03.

`GET /api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=brl,usd` (header
`x-cg-demo-api-key`). O mapa symbol→id vem de `settings.coingecko_ids` (config, não
hardcoded — CLAUDE.md). Único fetcher que popula `price_usd`. Retry 3x backoff 1/2/4;
fail-soft: 429/erro/símbolo desconhecido → omitido (o worker mantém o valor anterior,
cache agressivo via TTL de 2h).
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from config import settings

from .base import PriceQuote, with_retry

_BASE_URL = "https://api.coingecko.com/api/v3/simple/price"
_SOURCE = "coingecko"


class CoinGeckoFetcher:
    """Cota cripto via CoinGecko. `ids_map`/`client`/`sleep` injetáveis para teste."""

    def __init__(
        self,
        api_key: str | None = None,
        ids_map: dict[str, str] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.coingecko_api_key
        self._ids = ids_map if ids_map is not None else settings.coingecko_ids
        self._client = client
        self._sleep = sleep

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        # símbolo (UPPER) -> id CoinGecko; ignora os fora do mapa de config.
        sym_to_id = {s: self._ids[s.upper()] for s in symbols if s.upper() in self._ids}
        if not sym_to_id:
            return {}
        ids_param = ",".join(sorted(set(sym_to_id.values())))
        client = self._client or httpx.AsyncClient()
        try:
            data = await with_retry(
                lambda: self._request(client, ids_param),
                attempts=4,
                sleep=self._sleep,
            )
        except Exception:
            return {}  # fail-soft: cache agressivo (worker mantém o valor anterior)
        finally:
            if self._client is None:
                await client.aclose()

        out: dict[str, PriceQuote] = {}
        for sym, cid in sym_to_id.items():
            entry = data.get(cid) if isinstance(data, dict) else None
            if not isinstance(entry, dict):
                continue
            brl = entry.get("brl")
            if brl is None:
                continue
            usd = entry.get("usd")
            out[sym] = PriceQuote(
                price_brl=float(brl),
                price_usd=float(usd) if usd is not None else None,
                source=_SOURCE,
            )
        return out

    async def _request(self, client: httpx.AsyncClient, ids_param: str) -> Any:
        headers = {"x-cg-demo-api-key": self._api_key} if self._api_key else {}
        resp = await client.get(
            _BASE_URL,
            params={"ids": ids_param, "vs_currencies": "brl,usd"},
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
