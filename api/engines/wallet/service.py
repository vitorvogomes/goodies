"""Wallet Engine — escrita de saldos escaneados (m4, STORY-04-01).

`upsert_wallet_position` é o write path do worker `wallet_scan`: grava o snapshot mais
recente do saldo por (usuário, chain, endereço, ativo). Idempotente (ON CONFLICT): uma
nova varredura atualiza quantity/source e avança `scanned_at`, sem duplicar linhas.

Leitura valorada (`list_wallet_positions`) e reconciliação (`reconcile`) alimentam os
endpoints `/api/v1/wallets/*` (consumidos pelo frontend 04-10/04-11).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import asyncpg

from config import settings
from engines.market.fetchers.wallets.base import WalletBalance
from engines.portfolio.service import net_quantity


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


async def list_wallet_positions(
    conn: asyncpg.Connection, user_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Saldos escaneados do usuário, valorados pelo preço corrente (m3, asset_prices).

    `value_brl = quantity x price_brl` (None sem preço); `stale` = scan mais velho que
    `ttl_wallet`. Uma varredura do preço (asset_prices) p/ todos os símbolos (sem N+1).
    """
    now = now or datetime.now(tz=UTC)
    rows = await conn.fetch(
        "SELECT chain, wallet_address, asset_symbol, quantity, source, scanned_at "
        "FROM wallet_positions WHERE user_id = $1 ORDER BY chain, asset_symbol",
        user_id,
    )
    symbols = [r["asset_symbol"] for r in rows]
    prices: dict[str, float] = {}
    if symbols:
        price_rows = await conn.fetch(
            "SELECT ticker, price_brl FROM asset_prices WHERE ticker = ANY($1)", symbols
        )
        prices = {r["ticker"]: float(r["price_brl"]) for r in price_rows}
    out: list[dict[str, Any]] = []
    for r in rows:
        qty = float(r["quantity"])
        price = prices.get(r["asset_symbol"])
        scanned_at: datetime = r["scanned_at"]
        out.append(
            {
                "chain": r["chain"],
                "wallet_address": r["wallet_address"],
                "asset_symbol": r["asset_symbol"],
                "quantity": qty,
                "source": r["source"],
                "scanned_at": scanned_at.isoformat(),
                "price_brl": price,
                "value_brl": qty * price if price is not None else None,
                "stale": (now - scanned_at).total_seconds() > settings.ttl_wallet,
            }
        )
    return out


async def reconcile(conn: asyncpg.Connection, user_id: str) -> list[dict[str, Any]]:
    """Reconcilia saldo escaneado vs registrado: `delta = Σ scanned - net_quantity(ops)`.

    Por símbolo: soma a quantidade escaneada (todas as wallets) e compara com a quantidade
    líquida das `asset_operations` (reusa `portfolio.service.net_quantity`).
    """
    scanned_rows = await conn.fetch(
        "SELECT asset_symbol, SUM(quantity) AS qty FROM wallet_positions "
        "WHERE user_id = $1 GROUP BY asset_symbol",
        user_id,
    )
    scanned = {r["asset_symbol"]: float(r["qty"]) for r in scanned_rows}

    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade FROM asset_operations WHERE user_id = $1",
        user_id,
    )
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_symbol[op["asset_symbol"]].append(op)
    registered = {sym: net_quantity(rows) for sym, rows in by_symbol.items()}

    out: list[dict[str, Any]] = []
    for sym in sorted(set(scanned) | set(registered)):
        s = scanned.get(sym, 0.0)
        reg = registered.get(sym, 0.0)
        out.append(
            {
                "asset_symbol": sym,
                "scanned_quantity": s,
                "registered_quantity": reg,
                "delta": s - reg,
            }
        )
    return out
