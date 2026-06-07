"""Fetcher Binance — spot + Simple Earn. STORY-04-05. **Assinado (HMAC), cron-only.**

CLAUDE.md: Binance é **cron-only** (nunca on-demand — rate limit) e toda requisição é
**assinada** (HMAC-SHA256). Cron-only é estrutural: este fetcher só é referenciado por
`workers.wallet_workers.run_wallet_scan`; nenhum router o dispara.

Assinatura: query `timestamp={ms}&recvWindow={n}` → `signature = HMAC_SHA256(secret, query)`
anexado; header `X-MBX-APIKEY`. Endpoints:
  - spot:     `GET /api/v3/account` → `balances[{asset, free, locked}]`
  - earn flex:`GET /sapi/v1/simple-earn/flexible/position` → `rows[{asset, totalAmount}]`
  - earn lock:`GET /sapi/v1/simple-earn/locked/position`   → `rows[{asset, amount}]`
Agrega free+locked+earn por ativo; mantém só símbolos conhecidos (default = `coingecko_ids`,
i.e., os que têm preço no m3) — descarta dust. Devolve QUANTIDADES. Fail-soft por endpoint:
um endpoint fora não derruba os outros; tudo fora → lista vazia, nunca levanta.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from urllib.parse import urlencode

import httpx

from config import settings

from ..base import with_client
from .base import WalletBalance

_BASE_URL = "https://api.binance.com"
_SOURCE = "binance"
_CHAIN = "binance"


class BinanceFetcher:
    """Escaneia spot + earn na Binance (assinado). Args injetáveis p/ teste."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        *,
        symbols: Sequence[str] | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        base_url: str = _BASE_URL,
        clock: Callable[[], float] = time.time,
        recv_window: int = 5000,
    ) -> None:
        self._key = api_key if api_key is not None else settings.binance_api_key
        self._secret = api_secret if api_secret is not None else settings.binance_api_secret
        self._symbols = (
            {s.upper() for s in symbols}
            if symbols is not None
            else {s.upper() for s in settings.coingecko_ids}
        )
        self._client = client
        self._sleep = sleep
        self._base = base_url.rstrip("/")
        self._clock = clock
        self._recv = recv_window
        self._offset_ms = 0  # offset relógio local → servidor (calculado por fetch)

    async def fetch(self) -> list[WalletBalance]:
        if not self._key or not self._secret:
            return []  # sem credencial → no-op
        totals: dict[str, float] = defaultdict(float)
        endpoints: tuple[tuple[str, Callable[[Any, dict[str, float]], None]], ...] = (
            ("/api/v3/account", self._parse_spot),
            ("/sapi/v1/simple-earn/flexible/position", self._parse_flexible),
            ("/sapi/v1/simple-earn/locked/position", self._parse_locked),
        )
        client = self._client or httpx.AsyncClient()
        try:
            # corrige clock-skew (WSL): a Binance rejeita timestamp fora do recvWindow.
            self._offset_ms = await self._server_offset(client)
            for path, parser in endpoints:

                async def _req(c: httpx.AsyncClient, p: str = path) -> Any:
                    return await self._signed_get(c, p)

                try:
                    data = await with_client(_req, client=client, sleep=self._sleep)
                except Exception:
                    continue  # fail-soft por endpoint
                parser(data, totals)
        finally:
            if self._client is None:
                await client.aclose()
        return [
            WalletBalance(
                chain=_CHAIN,
                wallet_address=_CHAIN,
                asset_symbol=asset,
                quantity=qty,
                source=_SOURCE,
            )
            for asset, qty in sorted(totals.items())
            if asset in self._symbols and qty > 0
        ]

    async def _server_offset(self, client: httpx.AsyncClient) -> int:
        """`serverTime - relógio local` (ms). Fail-soft: `/time` fora → 0 (usa local)."""
        try:
            resp = await client.get(f"{self._base}/api/v3/time", timeout=10.0)
            resp.raise_for_status()
            return int(resp.json()["serverTime"]) - int(self._clock() * 1000)
        except Exception:
            return 0

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(params)
        sig = hmac.new(self._secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        return {**params, "signature": sig}

    async def _signed_get(self, client: httpx.AsyncClient, path: str) -> Any:
        timestamp = int(self._clock() * 1000) + self._offset_ms  # corrigido p/ o servidor
        params = {"timestamp": timestamp, "recvWindow": self._recv}
        resp = await client.get(
            f"{self._base}{path}",
            params=self._sign(params),
            headers={"X-MBX-APIKEY": self._key},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_spot(data: Any, totals: dict[str, float]) -> None:
        rows = data.get("balances", []) if isinstance(data, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset", "")).upper()
            if not asset:
                continue
            totals[asset] += float(row.get("free", 0) or 0) + float(row.get("locked", 0) or 0)

    @staticmethod
    def _parse_flexible(data: Any, totals: dict[str, float]) -> None:
        BinanceFetcher._parse_earn(data, totals, "totalAmount")

    @staticmethod
    def _parse_locked(data: Any, totals: dict[str, float]) -> None:
        BinanceFetcher._parse_earn(data, totals, "amount")

    @staticmethod
    def _parse_earn(data: Any, totals: dict[str, float], field: str) -> None:
        rows = data.get("rows", []) if isinstance(data, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset", "")).upper()
            if asset:
                totals[asset] += float(row.get(field, 0) or 0)
