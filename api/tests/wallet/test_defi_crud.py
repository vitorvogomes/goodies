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
async def test_requires_auth(api: httpx.AsyncClient, pool: Any) -> None:
    assert (await api.get("/api/v1/defi/positions")).status_code == 401
