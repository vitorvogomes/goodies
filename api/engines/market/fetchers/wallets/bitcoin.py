"""Fetcher Bitcoin mainchain — BTC nativo (Trust). **Client DEDICADO (ADR-005).**

ADR-005: a mainchain Bitcoin e a Liquid são redes DISTINTAS, com clients SEPARADOS — este
fetcher NÃO compartilha nada com o `LiquidFetcher`. Usa o esplora público da Blockstream na
mainchain: base `BTC_BASE_URL` = `https://blockstream.info/api` (NÃO `/liquid/api`) +
`WALLET_TRUST_BTC_ADDRESS` (endereço bc1q... da Trust).

Esplora API: `GET {base}/address/{addr}` → `{chain_stats: {funded_txo_sum, spent_txo_sum},
mempool_stats: {...}}`. O saldo CONFIRMADO = `funded_txo_sum - spent_txo_sum` (sats), /1e8 →
BTC (1 chamada, sem paginar UTXOs). Valoração reusa o m3 (`coingecko_ids["BTC"]="bitcoin"`).

Fail-soft: API fora → lista vazia, nunca levanta.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from config import settings

from ..base import with_client
from .base import ScanBalances, WalletBalance

_SOURCE = "bitcoin"
_CHAIN = "bitcoin"
_SYMBOL = "BTC"


class BitcoinFetcher:
    """Escaneia BTC mainchain (client dedicado, ADR-005). Args injetáveis p/ teste."""

    def __init__(
        self,
        base_url: str | None = None,
        address: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        base = base_url if base_url is not None else settings.btc_base_url
        self._base = base.rstrip("/")
        self._address = address if address is not None else settings.wallet_trust_btc_address
        self._client = client
        self._sleep = sleep

    async def fetch(self) -> list[WalletBalance]:
        if not self._address:
            # não escaneou (sem endereço) ≠ escaneou e não achou nada
            return ScanBalances(complete=False)
        try:
            data = await with_client(self._get_stats, client=self._client, sleep=self._sleep)
        except Exception:
            return ScanBalances(complete=False)  # fail-soft: fonte fora (sem sweep)
        stats = data.get("chain_stats") if isinstance(data, dict) else None
        if not isinstance(stats, dict):
            return ScanBalances(complete=False)
        funded = stats.get("funded_txo_sum")
        spent = stats.get("spent_txo_sum")
        if not isinstance(funded, int | float) or not isinstance(spent, int | float):
            return ScanBalances(complete=False)
        sats = int(funded) - int(spent)  # saldo confirmado (sats)
        if sats <= 0:
            return ScanBalances()  # escaneou e está zerado (BTC vendido) → sweep ok
        return ScanBalances(
            [
                WalletBalance(
                    chain=_CHAIN,
                    wallet_address=self._address,
                    asset_symbol=_SYMBOL,
                    quantity=sats / 1e8,
                    source=_SOURCE,
                )
            ]
        )

    async def _get_stats(self, client: httpx.AsyncClient) -> Any:
        resp = await client.get(f"{self._base}/address/{self._address}", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
