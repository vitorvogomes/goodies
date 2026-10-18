"""Story 3.2 — ativos com chave única: classe v2 em `common`, ativo novo nasce com a key do mapa,
alias por cadeia e key imutável."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from engines.common.assets import CATEGORIES, CLASS_BY_CATEGORY


@pytest.mark.asyncio
async def test_class_map_matches_the_database_function(pool: Any) -> None:
    async with pool.acquire() as conn:
        for category in CATEGORIES:
            assert await conn.fetchval("SELECT goodies_asset_class($1)", category) == str(
                CLASS_BY_CATEGORY[category]
            )


@pytest.mark.asyncio
async def test_new_operation_and_wallet_token_get_an_asset(pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    ticker = f"T{uuid.uuid4().hex[:4].upper()}3"
    token = f"TK{uuid.uuid4().hex[:4].upper()}"
    async with pool.acquire() as conn:
        try:
            op_asset = await conn.fetchval(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                "tipo, quantidade, valor_unitario, data_operacao) "
                "VALUES ($1, 'Toro/B3', $2, 'Ações Nacionais', 'compra', 1, 10, '2099-01-02') "
                "RETURNING asset_id",
                uid,
                ticker,
            )
            again = await conn.fetchval(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                "tipo, quantidade, valor_unitario, data_operacao) "
                "VALUES ($1, 'B3-movimentacao', $2, 'Ações Nacionais', 'compra', 1, 11, "
                "'2099-01-03') RETURNING asset_id",
                uid,
                ticker,
            )
            asset = await conn.fetchrow("SELECT * FROM assets WHERE id = $1", op_asset)
            assert again == op_asset  # mesmo ativo, outra corretora
            assert (asset["key"], asset["class"], asset["price_ref"]) == (
                f"b3:{ticker}",
                "acoes_br",
                ticker,
            )

            wallet_asset = await conn.fetchval(
                "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
                "quantity, source) VALUES ($1, 'solana', 'x', $2, 1, 'solana') RETURNING asset_id",
                uid,
                token,
            )
            assert (
                await conn.fetchval("SELECT key FROM assets WHERE id = $1", wallet_asset)
                == f"crypto:{token}"
            )
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("UPDATE assets SET key = 'b3:OUTRO' WHERE id = $1", op_asset)
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", ticker)
            await conn.execute("DELETE FROM wallet_positions WHERE asset_symbol = $1", token)
            await conn.execute(
                "DELETE FROM assets WHERE key = ANY($1::text[])",
                [f"b3:{ticker}", f"crypto:{token}"],
            )
