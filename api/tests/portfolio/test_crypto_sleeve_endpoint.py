"""Tests do endpoint GET /api/v1/portfolio/crypto-sleeve (m4).

O mesmo objeto serve a reconciliação de VALOR (net_invested vs current_value → resultado,
por rail). Tickers sintéticos (evita colisão no Redis compartilhado).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from auth.security import hash_password


async def _login(api: AsyncClient, email: str) -> dict[str, str]:
    resp = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": "sleeve-ep-test"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def crypto_user(pool: Any, api: AsyncClient) -> AsyncIterator[dict[str, Any]]:
    email = f"sleeve-ep-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email, hash_password("sleeve-ep-test"),
        )
        account_id = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ('Nubank EP', 'bank') RETURNING id"
        )
    headers = await _login(api, email)
    yield {"uid": str(uid), "account_id": account_id, "headers": headers, "pool": pool}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", account_id)
        await conn.execute("DELETE FROM accounts WHERE id = $1", account_id)
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", str(uid))
        await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", str(uid))
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


async def _tx(conn: Any, acc: uuid.UUID, amount: float, category: str) -> None:
    await conn.execute(
        "INSERT INTO transactions (account_id, date, amount, category, kind) "
        "VALUES ($1, $2, $3, $4, 'investment')",
        acc, date(2026, 1, 2), amount, category,
    )


async def _price(conn: Any, ticker: str, brl: float) -> None:
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ($1, $2, 'coingecko', false)",
        ticker, brl,
    )


async def _wallet(conn: Any, uid: str, chain: str, sym: str, qty: float) -> None:
    await conn.execute(
        "INSERT INTO wallet_positions "
        "(user_id, chain, wallet_address, asset_symbol, quantity, source, is_manual) "
        "VALUES ($1, $2, 'addr', $3, $4, 'etherscan', false)",
        uid, chain, sym, qty,
    )


async def _defi(conn: Any, uid: str, sym: str, bal: float) -> None:
    await conn.execute(
        "INSERT INTO defi_positions (user_id, protocol, asset_symbol, balance, is_active) "
        "VALUES ($1, 'hylo', $2, $3, true)",
        uid, sym, bal,
    )


class TestCryptoSleeveEndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/crypto-sleeve")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_empty(self, api: AsyncClient, crypto_user: dict) -> None:
        resp = await api.get(
            "/api/v1/portfolio/crypto-sleeve", headers=crypto_user["headers"]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_value_brl"] == 0.0
        assert data["net_invested_brl"] == 0.0
        assert data["resultado"] == 0.0
        assert data["xirr"] is None

    @pytest.mark.asyncio
    async def test_reconciliation_math(
        self, api: AsyncClient, crypto_user: dict
    ) -> None:
        pool, uid, acc = (
            crypto_user["pool"], crypto_user["uid"], crypto_user["account_id"]
        )
        async with pool.acquire() as conn:
            await _tx(conn, acc, -1000.0, "Binance")
            await _tx(conn, acc, -500.0, "Cripto Nubnak")
            await _tx(conn, acc, 100.0, "Binance")  # net_invested = 1400
            await _price(conn, "TKNA", 200.0)
            await _price(conn, "TKND", 4.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 3.0)  # 600
            await _defi(conn, uid, "TKND", 50.0)               # 200
        resp = await api.get(
            "/api/v1/portfolio/crypto-sleeve", headers=crypto_user["headers"]
        )
        assert resp.status_code == 200
        d = resp.json()
        assert abs(d["current_value_brl"] - 800.0) < 0.01
        assert abs(d["net_invested_brl"] - 1400.0) < 0.01
        assert abs(d["resultado"] - (d["current_value_brl"] - d["net_invested_brl"])) < 0.01
        assert abs(d["resultado"] - (-600.0)) < 0.01
        rail_sum = sum(r["current_value_brl"] for r in d["by_rail"])
        assert abs(rail_sum - d["current_value_brl"]) < 0.01

    @pytest.mark.asyncio
    async def test_misspelled_category_counted(
        self, api: AsyncClient, crypto_user: dict
    ) -> None:
        """'Cripto Nubnak' (typo real) entra no custo do sleeve."""
        pool, acc = crypto_user["pool"], crypto_user["account_id"]
        async with pool.acquire() as conn:
            await _tx(conn, acc, -300.0, "Cripto Nubnak")
        resp = await api.get(
            "/api/v1/portfolio/crypto-sleeve", headers=crypto_user["headers"]
        )
        assert abs(resp.json()["cost_basis_brl"] - 300.0) < 0.01
