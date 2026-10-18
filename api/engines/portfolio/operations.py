"""Asset operations engine — CRUD for buy/sell/dividend/interest transactions."""
from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg


async def create_operation(
    conn: asyncpg.Connection,
    user_id: str,
    broker: str,
    asset_symbol: str,
    asset_category: str,
    tipo: str,
    quantidade: float,
    valor_unitario: float,
    data_operacao: date,
    notes: str | None = None,
    external_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a new asset operation.

    Args:
        conn: DB connection
        user_id: User ID (UUID)
        broker: Broker name (B3, Binance, etc.)
        asset_symbol: Asset ticker (PETR4, BTC, etc.)
        asset_category: Asset category (Ações Nacionais, Cripto, etc.)
        tipo: Operation type (compra, venda, dividendo, juros, aporte, resgate)
        quantidade: Quantity (>0, NUMERIC(20,8))
        valor_unitario: Unit price (>=0, NUMERIC(15,6))
        data_operacao: Operation date
        notes: Optional notes
        external_id: Optional external identifier (e.g., broker order ID)

    Returns:
        Created operation dict with id, created_at, etc.

    Raises:
        asyncpg.CheckViolationError: If tipo invalid or constraints violated
        asyncpg.UniqueViolationError: If external_id already exists
    """
    query = """
        INSERT INTO asset_operations
        (user_id, broker, asset_symbol, asset_category, tipo, quantidade,
         valor_unitario, data_operacao, notes, external_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, user_id, broker, asset_symbol, asset_category, tipo,
                  quantidade, valor_unitario, data_operacao, notes, external_id,
                  created_at
    """
    row = await conn.fetchrow(
        query,
        user_id,
        broker,
        asset_symbol,
        asset_category,
        tipo,
        quantidade,
        valor_unitario,
        data_operacao,
        notes,
        external_id,
    )
    return dict(row) if row else {}


async def list_operations(
    conn: asyncpg.Connection,
    user_id: str,
    asset_symbol: str | None = None,
    tipo: str | None = None,
    data_from: date | None = None,
    data_to: date | None = None,
) -> list[dict[str, Any]]:
    """
    List operations with optional filters.

    Args:
        conn: DB connection
        user_id: User ID (UUID)
        asset_symbol: Filter by asset symbol (optional)
        tipo: Filter by operation type (optional)
        data_from: Filter by operation date >= data_from (optional)
        data_to: Filter by operation date <= data_to (optional)

    Returns:
        List of operation dicts, ordered by data_operacao DESC.
    """
    query = """
        SELECT id, user_id, broker, asset_symbol, asset_category, tipo,
               quantidade, valor_unitario, data_operacao, notes, external_id,
               created_at
        FROM asset_operations
        WHERE user_id = $1
    """
    params: list[Any] = [user_id]
    param_idx = 2

    if asset_symbol:
        # busca por similaridade: substring case-insensitive ('petr' acha PETR4F)
        query += f" AND asset_symbol ILIKE '%' || ${param_idx} || '%'"
        params.append(asset_symbol)
        param_idx += 1

    if tipo:
        query += f" AND tipo = ${param_idx}"
        params.append(tipo)
        param_idx += 1

    if data_from:
        query += f" AND data_operacao >= ${param_idx}"
        params.append(data_from)
        param_idx += 1

    if data_to:
        query += f" AND data_operacao <= ${param_idx}"
        params.append(data_to)
        param_idx += 1

    query += " ORDER BY data_operacao DESC"

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


