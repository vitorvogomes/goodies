"""Contrato dos fetchers de saldo de wallet (m4).

Diferente do `PriceFetcher` (preço por símbolo), o `BalanceFetcher` descobre as posições
on-chain/exchange por conta própria (a partir de um endereço/credencial em `settings`),
então `fetch()` não recebe `symbols`. Devolve QUANTIDADES — a valoração reusa o preço do
Market Engine (m3). Fail-soft (CLAUDE.md): qualquer falha de fonte externa → lista vazia.

Os fetchers concretos (B2) reusam `with_client` do scaffold do Market Engine:
    from ..base import with_client
"""
from __future__ import annotations

from collections.abc import Iterable
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


class ScanBalances(list[WalletBalance]):
    """Lista de saldos + completude do scan.

    `complete=False` quando alguma sub-unidade (spec/endereço/endpoint) falhou ou a
    fonte nem foi consultada (sem credencial/fora): o sweep NÃO pode tratar o que
    faltou como posição fechada (achado C5), e o worker reporta a falha nos stats.
    Subclasse de list de propósito: todo call site que itera/compara continua válido.
    """

    def __init__(
        self, balances: Iterable[WalletBalance] = (), *, complete: bool = True
    ) -> None:
        super().__init__(balances)
        self.complete = complete


class BalanceFetcher(Protocol):
    """Escaneia os saldos de uma fonte (fail-soft: fonte fora → lista vazia)."""

    async def fetch(self) -> list[WalletBalance]: ...
