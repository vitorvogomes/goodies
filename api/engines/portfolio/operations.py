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


async def get_operation(
    conn: asyncpg.Connection, user_id: str, operation_id: str
) -> dict[str, Any] | None:
    """
    Get a single operation by ID.

    Returns:
        Operation dict or None if not found/not owned by user.
    """
    query = """
        SELECT id, user_id, broker, asset_symbol, asset_category, tipo,
               quantidade, valor_unitario, data_operacao, notes, external_id,
               created_at
        FROM asset_operations
        WHERE id = $1 AND user_id = $2
    """
    row = await conn.fetchrow(
        query,
        operation_id,
        user_id,
    )
    return dict(row) if row else None


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
        query += f" AND asset_symbol = ${param_idx}"
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


async def update_operation(
    conn: asyncpg.Connection,
    user_id: str,
    operation_id: str,
    broker: str,
    asset_symbol: str,
    asset_category: str,
    tipo: str,
    quantidade: float,
    valor_unitario: float,
    data_operacao: date,
    notes: str | None = None,
    external_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Update an asset operation.

    Returns:
        Updated operation dict or None if not found/not owned by user.
    """
    query = """
        UPDATE asset_operations
        SET broker = $3, asset_symbol = $4, asset_category = $5, tipo = $6,
            quantidade = $7, valor_unitario = $8, data_operacao = $9,
            notes = $10, external_id = $11
        WHERE id = $1 AND user_id = $2
        RETURNING id, user_id, broker, asset_symbol, asset_category, tipo,
                  quantidade, valor_unitario, data_operacao, notes, external_id,
                  created_at
    """
    row = await conn.fetchrow(
        query,
        operation_id,
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
    return dict(row) if row else None


async def delete_operation(
    conn: asyncpg.Connection, user_id: str, operation_id: str
) -> bool:
    """
    Delete an asset operation.

    Returns:
        True if deleted, False if not found/not owned by user.
    """
    result = await conn.execute(
        "DELETE FROM asset_operations WHERE id = $1 AND user_id = $2",
        operation_id,
        user_id,
    )
    return bool(result != "DELETE 0")


async def calculate_dca_by_asset(
    conn: asyncpg.Connection, user_id: str, asset_symbol: str
) -> dict[str, Any] | None:
    """
    Calculate DCA (preço médio ponderado) for a single asset.

    Only includes 'compra' and 'aporte' tipos in calculation.
    Excludes 'venda', 'resgate', 'dividendo', 'juros'.

    Returns:
        Dict with asset_symbol, preco_medio, quantidade_total.
        None if no compra/aporte operations exist.
    """
    query = """
        SELECT
            asset_symbol,
            SUM(quantidade * valor_unitario) / SUM(quantidade) AS preco_medio,
            SUM(quantidade) AS quantidade_total
        FROM asset_operations
        WHERE user_id = $1
          AND asset_symbol = $2
          AND tipo IN ('compra', 'aporte')
        GROUP BY asset_symbol
    """
    row = await conn.fetchrow(query, user_id, asset_symbol)
    if row is None or row["preco_medio"] is None:
        return None
    return dict(row)


async def calculate_dca_all(
    conn: asyncpg.Connection, user_id: str
) -> list[dict[str, Any]]:
    """
    Calculate DCA for all assets with compra/aporte operations.

    Returns:
        List of dicts with asset_symbol, asset_category,
        preco_medio, quantidade_total. Empty list if no operations.
    """
    query = """
        SELECT
            asset_symbol,
            asset_category,
            SUM(quantidade * valor_unitario) / SUM(quantidade) AS preco_medio,
            SUM(quantidade) AS quantidade_total
        FROM asset_operations
        WHERE user_id = $1
          AND tipo IN ('compra', 'aporte')
        GROUP BY asset_symbol, asset_category
        ORDER BY asset_symbol
    """
    rows = await conn.fetch(query, user_id)
    return [dict(row) for row in rows]
