"""CRUD de posições DeFi (entrada manual) — STORY-04-08. Via ASGI."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from engines.market.cache import PriceCache
from engines.market.service import price_cache_key

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
async def test_put_clears_maturity_date(api: httpx.AsyncClient, wallet_user: dict) -> None:
    # PUT com maturity_date=null deve LIMPAR (COALESCE mantinha a data antiga → alerta fantasma)
    h = wallet_user["headers"]
    created = (
        await api.post(
            "/api/v1/defi/positions",
            json={"asset_symbol": "hyUSD-2609", "balance": 10.0, "maturity_date": "2026-09-29"},
            headers=h,
        )
    ).json()
    upd = await api.put(
        f"/api/v1/defi/positions/{created['id']}", json={"maturity_date": None}, headers=h
    )
    assert upd.status_code == 200
    assert upd.json()["maturity_date"] is None
    # campo ausente NÃO é alterado: balance segue 10
    assert upd.json()["balance"] == 10.0


@pytest.mark.asyncio
async def test_put_returns_valued_response(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    # update deve devolver price/value (não só o GET)
    h = wallet_user["headers"]
    created = (
        await api.post(
            "/api/v1/defi/positions", json={"asset_symbol": "MNL_HY", "balance": 1.0}, headers=h
        )
    ).json()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ('MNL_HY', 5.0, 'coingecko', false) ON CONFLICT (ticker) "
            "DO UPDATE SET price_brl = EXCLUDED.price_brl"
        )
    cache = PriceCache()
    await cache.delete(price_cache_key("crypto", "MNL_HY"))
    try:
        upd = await api.put(
            f"/api/v1/defi/positions/{created['id']}", json={"balance": 3.0}, headers=h
        )
        assert upd.json()["price_brl"] == 5.0
        assert upd.json()["value_brl"] == 15.0  # 3 x 5
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'MNL_HY'")


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
    # valoração é cache-aware (lê crypto cache antes do PG) — invalida p/ refletir o preço
    # recém-escrito (Redis é compartilhado; um smoke ao vivo pode ter deixado xSOL cacheado)
    cache = PriceCache()
    await cache.delete(price_cache_key("crypto", "xSOL"))
    await cache.delete(price_cache_key("crypto", "YT-xSOL-2609"))
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
