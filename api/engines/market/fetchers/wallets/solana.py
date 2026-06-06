"""Fetcher Solana — SOL nativo + tokens SPL. STORY-04-03.

Decisão: usamos o **JSON-RPC público da Solana** (`https://api.mainnet-beta.solana.com`),
não a Solscan Pro API. Motivo: o RPC é keyless, estável e documentado; o plano/endpoints
da Solscan v2 são incertos e exigiriam um plano pago confirmado. O `rpc_url` é injetável,
então trocar p/ um provider dedicado (Helius/QuickNode) depois é só configuração.

- SOL nativo: `getBalance` → lamports → /1e9.
- SPL: `getTokenAccountsByOwner` (jsonParsed) → casa o `mint` no mapa `mint→símbolo`
  (config-driven; mint desconhecido = dust → omitido), usa `tokenAmount.uiAmount`.

Devolve QUANTIDADES (o preço vem do m3). Fail-soft: RPC fora → lista vazia, nunca levanta.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from config import settings

from ..base import with_client
from .base import WalletBalance

_RPC_URL = "https://api.mainnet-beta.solana.com"
_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_SOURCE = "solana"
_CHAIN = "solana"

# mint SPL → símbolo (USDC/USDT na Solana). Injetável; mint fora do mapa é omitido.
_DEFAULT_MINTS: dict[str, str] = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
}


class SolanaFetcher:
    """Escaneia SOL + SPL via JSON-RPC. `mints`/`client`/`sleep`/`rpc_url` injetáveis."""

    def __init__(
        self,
        address: str | None = None,
        *,
        mints: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rpc_url: str = _RPC_URL,
    ) -> None:
        self._address = address if address is not None else settings.wallet_sol_address
        self._mints = mints if mints is not None else _DEFAULT_MINTS
        self._client = client
        self._sleep = sleep
        self._rpc = rpc_url

    async def fetch(self) -> list[WalletBalance]:
        if not self._address:
            return []
        out: list[WalletBalance] = []
        client = self._client or httpx.AsyncClient()
        try:
            try:
                sol = await with_client(self._get_balance, client=client, sleep=self._sleep)
                if sol > 0:
                    out.append(self._wb("SOL", sol))
            except Exception:
                pass  # fail-soft: SOL nativo fora não impede os SPL
            try:
                out.extend(
                    await with_client(self._get_tokens, client=client, sleep=self._sleep)
                )
            except Exception:
                pass  # fail-soft: SPL fora não impede o SOL já obtido
        finally:
            if self._client is None:
                await client.aclose()
        return out

    def _wb(self, symbol: str, qty: float) -> WalletBalance:
        return WalletBalance(
            chain=_CHAIN,
            wallet_address=self._address,
            asset_symbol=symbol,
            quantity=qty,
            source=_SOURCE,
        )

    async def _rpc_call(self, client: httpx.AsyncClient, method: str, params: Any) -> Any:
        resp = await client.post(
            self._rpc,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def _get_balance(self, client: httpx.AsyncClient) -> float:
        data = await self._rpc_call(client, "getBalance", [self._address])
        lamports = data["result"]["value"]  # KeyError em erro → fail-soft no chamador
        return float(lamports) / 1e9

    async def _get_tokens(self, client: httpx.AsyncClient) -> list[WalletBalance]:
        data = await self._rpc_call(
            client,
            "getTokenAccountsByOwner",
            [self._address, {"programId": _TOKEN_PROGRAM}, {"encoding": "jsonParsed"}],
        )
        out: list[WalletBalance] = []
        for acc in data["result"]["value"]:
            info = acc["account"]["data"]["parsed"]["info"]
            symbol = self._mints.get(info.get("mint", ""))
            if symbol is None:
                continue  # mint desconhecido (dust) omitido
            ui_amount = info.get("tokenAmount", {}).get("uiAmount")
            if ui_amount is None:
                continue
            qty = float(ui_amount)
            if qty > 0:
                out.append(self._wb(symbol, qty))
        return out
