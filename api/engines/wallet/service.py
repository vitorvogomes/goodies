"""Wallet Engine — escrita de saldos escaneados (m4, STORY-04-01).

`upsert_wallet_position` é o write path do worker `wallet_scan`: grava o snapshot mais
recente do saldo por (usuário, chain, endereço, ativo). Idempotente (ON CONFLICT): uma
nova varredura atualiza quantity/source e avança `scanned_at`, sem duplicar linhas.

Leitura valorada (`list_wallet_positions`) e reconciliação (`reconcile`) chegam com o
frontend (04-10/04-11).
"""
from __future__ import annotations

import asyncpg

from engines.market.fetchers.wallets.base import WalletBalance


async def upsert_wallet_position(
    conn: asyncpg.Connection, user_id: str, balance: WalletBalance
) -> None:
    """Grava/atualiza o saldo escaneado (snapshot mais recente) de um ativo numa wallet."""
    await conn.execute(
        """
        INSERT INTO wallet_positions
          (user_id, chain, wallet_address, asset_symbol, quantity, source, scanned_at)
        VALUES ($1, $2, $3, $4, $5, $6, now())
        ON CONFLICT (user_id, chain, wallet_address, asset_symbol) DO UPDATE
          SET quantity = EXCLUDED.quantity,
              source = EXCLUDED.source,
              scanned_at = now()
        """,
        user_id,
        balance.chain,
        balance.wallet_address,
        balance.asset_symbol,
        balance.quantity,
        balance.source,
    )
