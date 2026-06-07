"""CRUD de posições DeFi (entrada manual) — STORY-04-08. Via ASGI."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

_NEW = {
    "asset_symbol": "xSOL",
    "balance": 12.5,
    "protocol": "Phantom",
    "maturity_date": "2026-09-29",
    "notes": "staked SOL",
}


@pytest.mark.asyncio
async def test_create_and_list(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    resp = await api.post("/api/v1/defi/positions", json=_NEW, headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["asset_symbol"] == "xSOL"
    assert body["balance"] == 12.5
    assert body["maturity_date"] == "2026-09-29"

    listed = await api.get("/api/v1/defi/positions", headers=h)
    assert listed.status_code == 200
    assert [p["asset_symbol"] for p in listed.json()] == ["xSOL"]


@pytest.mark.asyncio
async def test_update(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    pid = (await api.post("/api/v1/defi/positions", json=_NEW, headers=h)).json()["id"]
    resp = await api.put(
        f"/api/v1/defi/positions/{pid}", json={"balance": 20.0, "is_active": False}, headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["balance"] == 20.0
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_list_filter_active(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    await api.post("/api/v1/defi/positions", json=_NEW, headers=h)
    await api.post(
        "/api/v1/defi/positions",
        json={"asset_symbol": "hyUSD", "balance": 5, "is_active": False},
        headers=h,
    )
    active = await api.get("/api/v1/defi/positions?active=true", headers=h)
    assert {p["asset_symbol"] for p in active.json()} == {"xSOL"}


@pytest.mark.asyncio
async def test_delete(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    pid = (await api.post("/api/v1/defi/positions", json=_NEW, headers=h)).json()["id"]
    assert (await api.delete(f"/api/v1/defi/positions/{pid}", headers=h)).status_code == 204
    assert (await api.delete(f"/api/v1/defi/positions/{pid}", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_negative_balance_rejected(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    resp = await api.post(
        "/api/v1/defi/positions", json={"asset_symbol": "xSOL", "balance": -1}, headers=h
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_values_positions_with_price(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    # xSOL com preço (alias CoinGecko) → valorado; YT-xSOL-2609 sem fonte → None (m4)
    h = wallet_user["headers"]
    await api.post(
        "/api/v1/defi/positions", json={"asset_symbol": "xSOL", "balance": 2.0}, headers=h
    )
    await api.post(
        "/api/v1/defi/positions",
        json={"asset_symbol": "YT-xSOL-2609", "balance": 100.0},
        headers=h,
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, price_usd, source, is_manual) "
            "VALUES ('xSOL', 1500.0, 280.0, 'coingecko', false) ON CONFLICT (ticker) "
            "DO UPDATE SET price_brl = EXCLUDED.price_brl, price_usd = EXCLUDED.price_usd"
        )
    try:
        listed = (await api.get("/api/v1/defi/positions", headers=h)).json()
        by = {p["asset_symbol"]: p for p in listed}
        assert by["xSOL"]["price_brl"] == 1500.0
        assert by["xSOL"]["value_brl"] == 3000.0  # 2 x 1500
        assert by["xSOL"]["value_usd"] == 560.0  # 2 x 280
        assert by["YT-xSOL-2609"]["price_brl"] is None  # sem fonte → não valorado
        assert by["YT-xSOL-2609"]["value_brl"] is None
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'xSOL'")


@pytest.mark.asyncio
async def test_requires_auth(api: httpx.AsyncClient, pool: Any) -> None:
    assert (await api.get("/api/v1/defi/positions")).status_code == 401
