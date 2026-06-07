"""Fetcher Etherscan (EVM) — ETH (mainnet) + ARB/ETH/PENDLE (Arbitrum). STORY-04-02 / m4.

Etherscan **V2 multichain** (uma só API key p/ todas as chains, parâmetro `chainid`):
`GET https://api.etherscan.io/v2/api?chainid={id}&module=account&action=...`. Saldo nativo
via `action=balance`; ERC-20 via `action=tokenbalance&contractaddress=...`. Cada spec é
(chain, chainid, símbolo, contrato|None, casas decimais). Devolve QUANTIDADES (saldo) —
o preço vem do Market Engine (m3, CoinGecko).

HYPE NÃO está aqui: fica na Hyperliquid L1 (fetcher dedicado `hyperliquid.py`).

Fail-soft (CLAUDE.md): a Etherscan responde HTTP 200 com `{"status":"0"}` em erro → o
`_balance` levanta p/ o `with_retry` reagir; spec que falha é omitida, nunca levanta.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, NamedTuple

import httpx

from config import settings

from ..base import with_client
from .base import WalletBalance

_BASE_URL = "https://api.etherscan.io/v2/api"
_SOURCE = "etherscan"


class _Spec(NamedTuple):
    chain: str
    chainid: int
    symbol: str
    contract: str | None  # None = saldo nativo (ETH); senão ERC-20
    decimals: int


# RABBY (mesmo endereço em todas as chains EVM): ETH nativo na mainnet (chainid 1) e na
# Arbitrum One (42161), + ARB e PENDLE (ERC-20) na Arbitrum. (HYPE → Hyperliquid L1.)
_DEFAULT_SPECS: tuple[_Spec, ...] = (
    _Spec("ethereum", 1, "ETH", None, 18),
    _Spec("arbitrum", 42161, "ARB", "0x912CE59144191C1204E64559FE8253a0e49E6548", 18),
    _Spec("arbitrum", 42161, "ETH", None, 18),
    _Spec("arbitrum", 42161, "PENDLE", "0x0c880f6761F1af8d9Aa9C466984b80DAb9a8c9e8", 18),
)


class EtherscanFetcher:
    """Escaneia saldos EVM via Etherscan V2. `specs`/`client`/`sleep` injetáveis p/ teste."""

    def __init__(
        self,
        api_key: str | None = None,
        address: str | None = None,
        *,
        specs: tuple[_Spec, ...] | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.etherscan_api_key
        self._address = address if address is not None else settings.wallet_rabby_address
        self._specs = specs if specs is not None else _DEFAULT_SPECS
        self._client = client
        self._sleep = sleep

    async def fetch(self) -> list[WalletBalance]:
        if not self._address:
            return []  # sem endereço configurado → no-op
        out: list[WalletBalance] = []
        client = self._client or httpx.AsyncClient()
        try:
            for spec in self._specs:

                async def _req(c: httpx.AsyncClient, s: _Spec = spec) -> float:
                    return await self._balance(c, s)

                try:
                    qty = await with_client(_req, client=client, sleep=self._sleep)
                except Exception:
                    continue  # fail-soft por spec: uma chain fora não derruba as outras
                if qty > 0:
                    out.append(
                        WalletBalance(
                            chain=spec.chain,
                            wallet_address=self._address,
                            asset_symbol=spec.symbol,
                            quantity=qty,
                            source=_SOURCE,
                        )
                    )
        finally:
            if self._client is None:
                await client.aclose()
        return out

    async def _balance(self, client: httpx.AsyncClient, spec: _Spec) -> float:
        params: dict[str, Any] = {
            "chainid": spec.chainid,
            "module": "account",
            "address": self._address,
            "tag": "latest",
            "apikey": self._api_key,
        }
        if spec.contract is None:
            params["action"] = "balance"
        else:
            params["action"] = "tokenbalance"
            params["contractaddress"] = spec.contract
        resp = await client.get(_BASE_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        # Etherscan: status "1" = OK; "0" = erro (apesar do HTTP 200). result = saldo bruto.
        if not isinstance(data, dict) or str(data.get("status")) != "1":
            msg = data.get("message") if isinstance(data, dict) else "resposta inesperada"
            raise ValueError(f"etherscan status != 1: {msg}")
        return float(int(data["result"]) / 10**spec.decimals)
