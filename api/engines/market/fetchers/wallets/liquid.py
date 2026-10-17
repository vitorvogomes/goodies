"""Fetcher Liquid Network — L-BTC + USDT (SideSwap). STORY-04-04. **Client DEDICADO (ADR-005).**

ADR-005 / CLAUDE.md: a Liquid é uma sidechain CONFIDENCIAL e distinta da mainchain
Bitcoin. É **proibido** reutilizar qualquer fetcher de Bitcoin mainchain. Este client é
dedicado e usa `LIQUID_BASE_URL` = `https://blockstream.info/liquid/api` (NÃO `/btc/api`)
+ `WALLET_SIDESWAP_ADDRESS` (endereço de recebimento do SideSwap) + os asset ids públicos
da Liquid: `LBTC_ASSET_ID` (L-BTC) e `LUSDT_ASSET_ID` (USDt na Liquid).

Esplora API: `GET {base}/address/{addr}/utxo` → lista de UTXOs `[{txid, vout, status,
value, asset}]`. A Liquid é multi-asset: soma `value` (sats) por asset, **somente** dos
assets conhecidos, e converte sats → quantidade (/1e8; L-BTC e USDt-na-Liquid têm precisão
8). Valoração reusa o m3: `coingecko_ids["L-BTC"]="bitcoin"` (1:1 BTC) e `["L-USDT"]=
"tether"`. Os dois saem sob o mesmo `source="liquid"` (o sweep varre os dois juntos).

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
from .base import ScanBalances, WalletBalance

_SOURCE = "liquid"
_CHAIN = "liquid"


class LiquidFetcher:
    """Escaneia L-BTC + USDT na Liquid (client dedicado, ADR-005). Args injetáveis p/ teste."""

    SOURCES = (_SOURCE,)  # fontes que um scan completo cobre (sweep de scan vazio)

    def __init__(
        self,
        base_url: str | None = None,
        address: str | None = None,
        *,
        assets: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        base = base_url if base_url is not None else settings.liquid_base_url
        self._base = base.rstrip("/")
        # asset_id -> símbolo; descarta ids vazios (asset não configurado no .env).
        raw = (
            assets
            if assets is not None
            else {settings.lbtc_asset_id: "L-BTC", settings.lusdt_asset_id: "L-USDT"}
        )
        self._assets = {aid: sym for aid, sym in raw.items() if aid}
        self._address = address if address is not None else settings.wallet_sideswap_address
        self._client = client
        self._sleep = sleep

    async def fetch(self) -> list[WalletBalance]:
        if not self._address or not self._assets:
            # não escaneou (sem endereço/asset) ≠ escaneou e não achou nada
            return ScanBalances(complete=False)
        try:
            utxos = await with_client(self._get_utxos, client=self._client, sleep=self._sleep)
        except Exception:
            return ScanBalances(complete=False)  # fail-soft: fonte fora (sem sweep)
        sats_by_asset: dict[str, int] = {}
        for utxo in utxos if isinstance(utxos, list) else []:
            # a Liquid é multi-asset; só conta os assets conhecidos (L-BTC / USDT).
            if not isinstance(utxo, dict):
                continue
            asset_id = utxo.get("asset")
            if asset_id not in self._assets:
                continue
            value = utxo.get("value")
            if isinstance(value, int | float):
                sats_by_asset[asset_id] = sats_by_asset.get(asset_id, 0) + int(value)
        out = ScanBalances()
        for asset_id, symbol in self._assets.items():  # ordem estável: L-BTC, L-USDT
            sats = sats_by_asset.get(asset_id, 0)
            if sats <= 0:
                continue
            out.append(
                WalletBalance(
                    chain=_CHAIN,
                    wallet_address=self._address,
                    asset_symbol=symbol,
                    quantity=sats / 1e8,
                    source=_SOURCE,
                )
            )
        return out

    async def _get_utxos(self, client: httpx.AsyncClient) -> Any:
        resp = await client.get(f"{self._base}/address/{self._address}/utxo", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
