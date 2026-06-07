"""Fetcher Liquid Network — L-BTC. STORY-04-04. **Client DEDICADO (ADR-005).**

ADR-005 / CLAUDE.md: a Liquid é uma sidechain CONFIDENCIAL e distinta da mainchain
Bitcoin. É **proibido** reutilizar qualquer fetcher de Bitcoin mainchain. Este client é
dedicado e usa `LIQUID_BASE_URL` = `https://blockstream.info/liquid/api` (NÃO `/btc/api`)
+ `LBTC_ASSET_ID` (constante pública da Liquid) + `WALLET_LIQUID_ADDRESS`.

Esplora API: `GET {base}/address/{addr}/utxo` → lista de UTXOs `[{txid, vout, status,
value, asset}]`. Soma `value` (sats) **somente** dos UTXOs cujo `asset == LBTC_ASSET_ID`
(a Liquid é multi-asset; outros assets são ignorados), e converte sats → L-BTC (/1e8). A
valoração reusa 1:1 com BTC (`coingecko_ids["L-BTC"] = "bitcoin"`, m3).

Fail-soft: API fora → lista vazia, nunca levanta. (Endereço confidencial/blinded sem
chave de visão não revela `value`/`asset` — a validar com o endereço real no ambiente.)
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from config import settings

from ..base import with_client
from .base import WalletBalance

_SOURCE = "liquid"
_CHAIN = "liquid"
_SYMBOL = "L-BTC"


class LiquidFetcher:
    """Escaneia L-BTC na Liquid (client dedicado, ADR-005). Args injetáveis p/ teste."""

    def __init__(
        self,
        base_url: str | None = None,
        asset_id: str | None = None,
        address: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        base = base_url if base_url is not None else settings.liquid_base_url
        self._base = base.rstrip("/")
        self._asset_id = asset_id if asset_id is not None else settings.lbtc_asset_id
        self._address = address if address is not None else settings.wallet_sideswap_address
        self._client = client
        self._sleep = sleep

    async def fetch(self) -> list[WalletBalance]:
        if not self._address or not self._asset_id:
            return []  # sem endereço/asset configurado → no-op
        try:
            utxos = await with_client(self._get_utxos, client=self._client, sleep=self._sleep)
        except Exception:
            return []  # fail-soft: fonte fora → nada
        sats = 0
        for utxo in utxos if isinstance(utxos, list) else []:
            # só conta UTXOs do asset L-BTC (a Liquid é multi-asset; ignora o resto).
            if not isinstance(utxo, dict) or utxo.get("asset") != self._asset_id:
                continue
            value = utxo.get("value")
            if isinstance(value, int | float):
                sats += int(value)
        if sats <= 0:
            return []
        return [
            WalletBalance(
                chain=_CHAIN,
                wallet_address=self._address,
                asset_symbol=_SYMBOL,
                quantity=sats / 1e8,
                source=_SOURCE,
            )
        ]

    async def _get_utxos(self, client: httpx.AsyncClient) -> Any:
        resp = await client.get(f"{self._base}/address/{self._address}/utxo", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
