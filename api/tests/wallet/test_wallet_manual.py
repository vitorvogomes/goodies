"""Posições manuais em wallet_positions (Liquid confidencial, não escaneável) — m4."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from workers.wallet_workers import run_wallet_scan


class _FakeFetcher:
    def __init__(self, balances: list[WalletBalance]) -> None:
        self._b = balances

    async def fetch(self) -> list[WalletBalance]:
        return self._b


@pytest.mark.asyncio
async def test_create_manual_position_appears_in_list(api: Any, wallet_user: dict) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.25},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 200
    pos = await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])
    rows = {p["asset_symbol"]: p for p in pos.json()}
    assert rows["L-BTC"]["is_manual"] is True
    assert rows["L-BTC"]["quantity"] == pytest.approx(0.25)
    assert rows["L-BTC"]["chain"] == "liquid"


@pytest.mark.asyncio
async def test_manual_upsert_is_idempotent(api: Any, wallet_user: dict, pool: Any) -> None:
    uid = wallet_user["user_id"]
    for qty in (1.0, 2.5):
        await api.post(
            "/api/v1/wallets/positions/manual",
            json={"chain": "liquid", "asset_symbol": "L-USDT", "quantity": qty},
            headers=wallet_user["headers"],
        )
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1 "
            "AND asset_symbol = 'L-USDT'",
            uid,
        )
        q = await conn.fetchval(
            "SELECT quantity FROM wallet_positions WHERE user_id = $1 "
            "AND asset_symbol = 'L-USDT'",
            uid,
        )
    assert n == 1  # upsert: uma linha só
    assert float(q) == pytest.approx(2.5)  # última quantidade vence


@pytest.mark.asyncio
async def test_delete_manual_position(api: Any, wallet_user: dict) -> None:
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.1},
        headers=wallet_user["headers"],
    )
    d = await api.delete(
        "/api/v1/wallets/positions/manual/liquid/L-BTC", headers=wallet_user["headers"]
    )
    assert d.status_code == 204
    d2 = await api.delete(
        "/api/v1/wallets/positions/manual/liquid/L-BTC", headers=wallet_user["headers"]
    )
    assert d2.status_code == 404  # já removida


@pytest.mark.asyncio
async def test_sweep_preserves_manual(api: Any, wallet_user: dict, pool: Any) -> None:
    # posição manual de Liquid sobrevive a um scan que cobre o source 'liquid'
    uid = wallet_user["user_id"]
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.3},
        headers=wallet_user["headers"],
    )
    fetcher = _FakeFetcher([WalletBalance("liquid", "lqADDR", "L-OTHER", 1.0, "liquid")])
    await run_wallet_scan(pool, uid, fetchers=[fetcher])
    async with pool.acquire() as conn:
        rows = [
            r["asset_symbol"]
            for r in await conn.fetch(
                "SELECT asset_symbol FROM wallet_positions WHERE user_id = $1 "
                "ORDER BY asset_symbol",
                uid,
            )
        ]
    assert "L-BTC" in rows  # manual preservada (não varrida)
    assert "L-OTHER" in rows  # escaneada gravada


@pytest.mark.asyncio
async def test_manual_position_rejects_negative(api: Any, wallet_user: dict) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": -1},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_manual_requires_auth(api: Any) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.1},
    )
    assert r.status_code in (401, 403)
