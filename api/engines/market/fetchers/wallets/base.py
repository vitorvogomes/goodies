"""Contrato dos fetchers de saldo de wallet (m4).

Diferente do `PriceFetcher` (preço por símbolo), o `BalanceFetcher` descobre as posições
on-chain/exchange por conta própria (a partir de um endereço/credencial em `settings`),
então `fetch()` não recebe `symbols`. Devolve QUANTIDADES — a valoração reusa o preço do
Market Engine (m3). Fail-soft (CLAUDE.md): qualquer falha de fonte externa → lista vazia.

Os fetchers concretos (B2) reusam `with_client` do scaffold do Market Engine:
    from ..base import with_client
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WalletBalance:
    """Saldo normalizado de um ativo numa wallet (quantidade, não preço)."""

    chain: str  # ethereum|arbitrum|solana|liquid|binance
    wallet_address: str  # endereço on-chain, ou 'binance' p/ a exchange
    asset_symbol: str  # ETH|ARB|HYPE|SOL|L-BTC|USDT...
    quantity: float
    source: str  # etherscan|solscan|liquid|binance


class BalanceFetcher(Protocol):
    """Escaneia os saldos de uma fonte (fail-soft: fonte fora → lista vazia)."""

    async def fetch(self) -> list[WalletBalance]: ...
