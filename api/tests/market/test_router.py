"""Endpoints /api/v1/market/* (STORY-03-08/09). Usa as fixtures de portfolio (auth)."""

from __future__ import annotations

from typing import Any

import pytest

from engines.common.cache import cache


@pytest.mark.asyncio
async def test_requires_auth(api: Any) -> None:
    resp = await api.get("/api/v1/market/prices")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_unknown_ticker_is_stale_null(api: Any, portfolio_user: dict) -> None:
    resp = await api.get("/api/v1/market/prices/MKT_UNKNOWN", headers=portfolio_user["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_brl"] is None
    assert body["stale"] is True


@pytest.mark.asyncio
async def test_post_manual_then_get(api: Any, portfolio_user: dict) -> None:
    headers = portfolio_user["headers"]
    resp = await api.post(
        "/api/v1/market/prices/MKT_MANUAL", json={"price_brl": 12.5}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_brl"] == 12.5
    assert body["is_manual"] is True
    assert body["stale"] is False

    got = await api.get("/api/v1/market/prices/MKT_MANUAL", headers=headers)
    assert got.json()["price_brl"] == 12.5


@pytest.mark.asyncio
async def test_manual_overrides_cached_auto_price(
    api: Any, pool: Any, portfolio_user: dict
) -> None:
    """Manual sempre vence: o POST invalida o cache Redis do preço de mercado."""
    from engines.market import service

    uid, headers = portfolio_user["user_id"], portfolio_user["headers"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'MKT_OVR', 'Ações Nacionais', 'compra', 10, 5, '2026-01-01')",
            uid,
        )
        # preço de mercado em cache + Postgres (como o worker grava)
        await service.cache_aside_write(
            conn,
            "MKT_OVR",
            cache_type="b3",
            price_brl=30.0,
            price_usd=None,
            source="brapi",
            ttl=300,
        )
    try:
        # override manual
        await api.post("/api/v1/market/prices/MKT_OVR", json={"price_brl": 40.0}, headers=headers)
        got = await api.get("/api/v1/market/prices/MKT_OVR", headers=headers)
        body = got.json()
        assert body["price_brl"] == 40.0  # manual, não os 30.0 cacheados
        assert body["is_manual"] is True
    finally:
        await cache().delete(service.price_cache_key("b3", "MKT_OVR"))


@pytest.mark.asyncio
async def test_revert_manual_price_to_auto(api: Any, pool: Any, portfolio_user: dict) -> None:
    """DELETE .../manual libera o ticker p/ o worker sobrescrever (is_manual=false),
    sem apagar o preço. Idempotente; 404 se o ticker não existe."""
    headers = portfolio_user["headers"]
    # 404 quando não há linha
    miss = await api.delete("/api/v1/market/prices/MKT_NONE/manual", headers=headers)
    assert miss.status_code == 404

    await api.post("/api/v1/market/prices/MKT_REV", json={"price_brl": 99.0}, headers=headers)
    resp = await api.delete("/api/v1/market/prices/MKT_REV/manual", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_manual"] is False  # liberado p/ o worker
    async with pool.acquire() as conn:
        flag = await conn.fetchval("SELECT is_manual FROM asset_prices WHERE ticker = 'MKT_REV'")
    assert flag is False
    # preço preservado (não apagado)
    got = await api.get("/api/v1/market/prices/MKT_REV", headers=headers)
    assert got.json()["price_brl"] == 99.0
    # idempotente: reverter de novo continua 200
    again = await api.delete("/api/v1/market/prices/MKT_REV/manual", headers=headers)
    assert again.status_code == 200


@pytest.mark.asyncio
async def test_revert_manual_rejected_without_market_source(
    api: Any, pool: Any, portfolio_user: dict
) -> None:
    """Review m4→main: caixinha/Renda Fixa não têm fetcher — liberar o is_manual deixaria
    o preço stale para sempre. Reverter é 409 e a flag continua true."""
    uid = portfolio_user["user_id"]
    headers = portfolio_user["headers"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'MKT_RFCX', 'Renda Fixa', 'compra', 1, 100, '2026-01-01')",
            uid,
        )
    await api.post("/api/v1/market/prices/MKT_RFCX", json={"price_brl": 105.0}, headers=headers)
    resp = await api.delete("/api/v1/market/prices/MKT_RFCX/manual", headers=headers)
    assert resp.status_code == 409
    async with pool.acquire() as conn:
        flag = await conn.fetchval("SELECT is_manual FROM asset_prices WHERE ticker = 'MKT_RFCX'")
    assert flag is True


@pytest.mark.asyncio
async def test_list_prices_covers_holdings(api: Any, pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    headers = portfolio_user["headers"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'MKT_HELD', 'Ações Nacionais', 'compra', 10, 5, '2026-01-01')",
            uid,
        )
    # sem preço ainda -> aparece na lista como stale/null
    resp = await api.get("/api/v1/market/prices", headers=headers)
    assert resp.status_code == 200
    prices = {p["ticker"]: p for p in resp.json()["prices"]}
    assert "MKT_HELD" in prices
    assert prices["MKT_HELD"]["stale"] is True
