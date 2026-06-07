"""Endpoints de leitura de wallet (positions/reconciliation) — STORY-04-10/04-11."""
from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from engines.wallet import service


async def _scan(pool: Any, uid: str, *balances: WalletBalance) -> None:
    async with pool.acquire() as conn:
        for b in balances:
            await service.upsert_wallet_position(conn, uid, b)


async def _price(pool: Any, ticker: str, price_brl: float) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ($1, $2, 'coingecko', false) ON CONFLICT (ticker) DO UPDATE "
            "SET price_brl = EXCLUDED.price_brl",
            ticker,
            price_brl,
        )


async def _op(pool: Any, uid: str, sym: str, tipo: str, qty: float) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', $2, 'Cripto', $3, $4, 1, $5)",
            uid,
            sym,
            tipo,
            qty,
            date(2026, 1, 1),
        )


@pytest.mark.asyncio
async def test_positions_valued_by_market_price(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    uid = wallet_user["user_id"]
    await _scan(pool, uid, WalletBalance("solana", "sol1", "MKT_WSOL", 3.0, "solana"))
    await _price(pool, "MKT_WSOL", 800.0)
    try:
        resp = await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])
        assert resp.status_code == 200
        pos = resp.json()
        assert len(pos) == 1
        assert pos[0]["asset_symbol"] == "MKT_WSOL"
        assert pos[0]["quantity"] == 3.0
        assert pos[0]["price_brl"] == 800.0
        assert pos[0]["value_brl"] == 2400.0  # 3 x 800
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'MKT_WSOL'")


@pytest.mark.asyncio
async def test_positions_without_price_null_value(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    uid = wallet_user["user_id"]
    await _scan(pool, uid, WalletBalance("liquid", "lq1", "MKT_WNOPX", 0.5, "liquid"))
    resp = await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])
    body = resp.json()
    assert body[0]["price_brl"] is None
    assert body[0]["value_brl"] is None


@pytest.mark.asyncio
async def test_reconciliation_delta(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    uid = wallet_user["user_id"]
    # escaneado 1.5 SOL; registrado net = 2 compra - 0.5 venda = 1.5 → delta 0
    await _scan(pool, uid, WalletBalance("solana", "sol1", "MKT_RSOL", 1.5, "solana"))
    await _op(pool, uid, "MKT_RSOL", "compra", 2.0)
    await _op(pool, uid, "MKT_RSOL", "venda", 0.5)
    # escaneado 0.2 L-BTC sem op → delta 0.2 (posição não registrada)
    await _scan(pool, uid, WalletBalance("liquid", "lq1", "MKT_RLBTC", 0.2, "liquid"))
    resp = await api.get("/api/v1/wallets/reconciliation", headers=wallet_user["headers"])
    assert resp.status_code == 200
    by = {r["asset_symbol"]: r for r in resp.json()}
    assert by["MKT_RSOL"]["delta"] == pytest.approx(0.0)
    assert by["MKT_RSOL"]["registered_quantity"] == pytest.approx(1.5)
    assert by["MKT_RLBTC"]["delta"] == pytest.approx(0.2)
    assert by["MKT_RLBTC"]["registered_quantity"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_read_endpoints_require_auth(api: httpx.AsyncClient) -> None:
    assert (await api.get("/api/v1/wallets/positions")).status_code == 401
    assert (await api.get("/api/v1/wallets/reconciliation")).status_code == 401
