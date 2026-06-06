"""Endpoints /api/v1/market/* (STORY-03-08/09). Usa as fixtures de portfolio (auth)."""
from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_requires_auth(api: Any) -> None:
    resp = await api.get("/api/v1/market/prices")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_unknown_ticker_is_stale_null(api: Any, portfolio_user: dict) -> None:
    resp = await api.get(
        "/api/v1/market/prices/MKT_UNKNOWN", headers=portfolio_user["headers"]
    )
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
            conn, "MKT_OVR", cache_type="b3", price_brl=30.0,
            price_usd=None, source="brapi", ttl=300,
        )
    try:
        # override manual
        await api.post(
            "/api/v1/market/prices/MKT_OVR", json={"price_brl": 40.0}, headers=headers
        )
        got = await api.get("/api/v1/market/prices/MKT_OVR", headers=headers)
        body = got.json()
        assert body["price_brl"] == 40.0  # manual, não os 30.0 cacheados
        assert body["is_manual"] is True
    finally:
        await service._cache.delete(service.price_cache_key("b3", "MKT_OVR"))


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
