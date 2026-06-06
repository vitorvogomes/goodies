"""Fetcher Hyperliquid L1 — HYPE (spot). STORY-04-02.

HYPE não é ERC-20 na Ethereum/Arbitrum: fica na Hyperliquid L1. A posição spot vem do
Info API: `POST https://api.hyperliquid.xyz/info` com `{"type":"spotClearinghouseState",
"user":<endereço>}` → `{"balances":[{"coin":"HYPE","total":"...","hold":"..."}]}`. O
endereço é o mesmo EVM (`WALLET_EVM_ADDRESS`; a Hyperliquid usa endereços EVM).

Devolve QUANTIDADES (o preço vem do m3 via `coingecko_ids["HYPE"]`). Fail-soft: API fora
→ lista vazia, nunca levanta.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from config import settings

from ..base import with_client
from .base import WalletBalance

_BASE_URL = "https://api.hyperliquid.xyz/info"
_SOURCE = "hyperliquid"
_CHAIN = "hyperliquid"


class HyperliquidFetcher:
    """Escaneia saldo spot na Hyperliquid. `symbols`/`client`/`sleep` injetáveis p/ teste."""

    def __init__(
        self,
        address: str | None = None,
        *,
        symbols: Sequence[str] = ("HYPE",),
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        base_url: str = _BASE_URL,
    ) -> None:
        self._address = address if address is not None else settings.wallet_evm_address
        self._symbols = {s.upper() for s in symbols}
        self._client = client
        self._sleep = sleep
        self._base = base_url

    async def fetch(self) -> list[WalletBalance]:
        if not self._address:
            return []
        try:
            data = await with_client(self._request, client=self._client, sleep=self._sleep)
        except Exception:
            return []  # fail-soft: API fora → nada
        out: list[WalletBalance] = []
        balances = data.get("balances", []) if isinstance(data, dict) else []
        for bal in balances:
            if not isinstance(bal, dict):
                continue
            coin = str(bal.get("coin", "")).upper()
            total = bal.get("total")
            if coin not in self._symbols or total is None:
                continue
            try:
                qty = float(total)
            except (TypeError, ValueError):
                continue
            if qty > 0:
                out.append(
                    WalletBalance(
                        chain=_CHAIN,
                        wallet_address=self._address,
                        asset_symbol=coin,
                        quantity=qty,
                        source=_SOURCE,
                    )
                )
        return out

    async def _request(self, client: httpx.AsyncClient) -> Any:
        resp = await client.post(
            self._base,
            json={"type": "spotClearinghouseState", "user": self._address},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
