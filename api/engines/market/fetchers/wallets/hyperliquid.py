"""Fetcher Hyperliquid — HYPE em DOIS lugares no mesmo endereço Rabby. STORY-04-02 / m4.

HYPE não é ERC-20 na Ethereum/Arbitrum. O fetcher soma duas fontes (fail-soft independente):
1. **L1 spot** — Info API `POST https://api.hyperliquid.xyz/info` com
   `{"type":"spotClearinghouseState","user":<addr>}` → `balances[].coin=="HYPE"` (chain
   `hyperliquid`).
2. **HyperEVM** — HYPE é o gas token NATIVO da chain EVM da Hyperliquid; o saldo spot NÃO o
   inclui. `eth_getBalance` no RPC `hyperevm_rpc_url` (wei/1e18, chain `hyperevm`).

Mesmo endereço EVM da Rabby (`WALLET_RABBY_ADDRESS`). Devolve QUANTIDADES (preço vem do m3
via `coingecko_ids["HYPE"]`). Fail-soft: cada fonte fora → omitida, nunca levanta 5xx.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from config import settings

from ..base import with_client
from .base import ScanBalances, WalletBalance

_BASE_URL = "https://api.hyperliquid.xyz/info"
_SOURCE = "hyperliquid"
_CHAIN = "hyperliquid"
_EVM_CHAIN = "hyperevm"
# Source DISTINTO do spot: o sweep (snapshot-replace) é por source. Se as duas fontes
# (spot L1 + HyperEVM) compartilhassem o source, uma cair (devolve []) enquanto a outra
# responde varreria o último snapshot bom da que caiu (outage ≠ posição fechada).
_EVM_SOURCE = "hyperevm"


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
        hyperevm_rpc_url: str | None = None,
    ) -> None:
        self._address = address if address is not None else settings.wallet_rabby_address
        self._symbols = {s.upper() for s in symbols}
        self._client = client
        self._sleep = sleep
        self._base = base_url
        self._evm_rpc = (
            hyperevm_rpc_url if hyperevm_rpc_url is not None else settings.hyperevm_rpc_url
        )

    async def fetch(self) -> list[WalletBalance]:
        if not self._address:
            # não escaneou (sem endereço) ≠ escaneou e não achou nada
            return ScanBalances(complete=False)
        # duas fontes independentes: L1 spot + HyperEVM nativo (fail-soft por fonte)
        spot = await self._fetch_spot()
        evm = await self._fetch_hyperevm()
        return ScanBalances([*spot, *evm], complete=spot.complete and evm.complete)

    async def _fetch_spot(self) -> ScanBalances:
        try:
            data = await with_client(self._request, client=self._client, sleep=self._sleep)
        except Exception:
            return ScanBalances(complete=False)  # fail-soft: API fora → nada (sem sweep)
        out = ScanBalances()
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

    async def _fetch_hyperevm(self) -> ScanBalances:
        """HYPE nativo na HyperEVM (gas token, 18 casas) via `eth_getBalance`."""
        if "HYPE" not in self._symbols:
            return ScanBalances()  # config deliberada: nada a buscar aqui
        if not self._evm_rpc:
            return ScanBalances(complete=False)  # não escaneou (RPC não configurado)
        try:
            data = await with_client(
                self._request_hyperevm, client=self._client, sleep=self._sleep
            )
        except Exception:
            return ScanBalances(complete=False)  # fail-soft (sem sweep deste scan)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, str):
            return ScanBalances(complete=False)
        try:
            qty = int(result, 16) / 1e18
        except (TypeError, ValueError):
            return ScanBalances(complete=False)
        if qty <= 0:
            return ScanBalances()
        return ScanBalances(
            [
                WalletBalance(
                    chain=_EVM_CHAIN,
                    wallet_address=self._address,
                    asset_symbol="HYPE",
                    quantity=qty,
                    source=_EVM_SOURCE,  # sweep independente do spot (ver _EVM_SOURCE)
                )
            ]
        )

    async def _request(self, client: httpx.AsyncClient) -> Any:
        resp = await client.post(
            self._base,
            json={"type": "spotClearinghouseState", "user": self._address},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def _request_hyperevm(self, client: httpx.AsyncClient) -> Any:
        resp = await client.post(
            self._evm_rpc,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBalance",
                "params": [self._address, "latest"],
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
