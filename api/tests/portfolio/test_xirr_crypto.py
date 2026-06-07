"""Fold do sleeve cripto no XIRR (m4, Fase 4): by_category["Cripto"] + consolidado.

O sleeve não vem de asset_operations — os cashflows são do ledger (custo) + valor atual das
carteiras. Usa usuário de uuid fresco por teste (dribla o cache de XIRR por usuário).
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


@pytest_asyncio.fixture
async def xirr_user(pool: Any, api: AsyncClient) -> AsyncIterator[dict[str, Any]]:
    email = f"xirr-cripto-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email, hash_password("xirr-test"),
        )
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ('Nubank Xirr', 'bank') RETURNING id"
        )
    resp = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": "xirr-test"}
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    yield {"uid": str(uid), "account_id": acc, "headers": headers, "pool": pool}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
        await conn.execute("DELETE FROM asset_operations WHERE user_id = $1", str(uid))
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", str(uid))
        await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", str(uid))
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


async def _seed_sleeve(conn: Any, uid: str, acc: uuid.UUID, *, qty: float) -> None:
    """Aporte -1000 há ~1 ano + valor atual = qty (preço 1.0)."""
    await conn.execute(
        "INSERT INTO transactions (account_id, date, amount, category, kind) "
        "VALUES ($1, $2, -1000.0, 'Binance', 'investment')",
        acc, date(2025, 6, 7),
    )
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ('TKNA', 1.0, 'coingecko', false)"
    )
    await conn.execute(
        "INSERT INTO wallet_positions "
        "(user_id, chain, wallet_address, asset_symbol, quantity, source, is_manual) "
        "VALUES ($1, 'ethereum', 'addr', 'TKNA', $2, 'etherscan', false)",
        uid, qty,
    )


class TestXirrCryptoFold:
    @pytest.mark.asyncio
    async def test_sleeve_in_by_category(
        self, api: AsyncClient, xirr_user: dict
    ) -> None:
        """Ganho (1100 vs 1000 investido) → by_category['Cripto'] positivo, não-nulo."""
        async with xirr_user["pool"].acquire() as conn:
            await _seed_sleeve(conn, xirr_user["uid"], xirr_user["account_id"], qty=1100.0)
        resp = await api.get("/api/v1/portfolio/xirr", headers=xirr_user["headers"])
        assert resp.status_code == 200
        by_cat = resp.json()["by_category"]
        assert "Cripto" in by_cat
        assert by_cat["Cripto"] is not None
        assert by_cat["Cripto"] > 0  # ganho

    @pytest.mark.asyncio
    async def test_consolidated_is_sleeve_when_only_crypto(
        self, api: AsyncClient, xirr_user: dict
    ) -> None:
        """Sem asset_operations, o consolidado = XIRR do sleeve (prova o fold no consolidado)."""
        async with xirr_user["pool"].acquire() as conn:
            await _seed_sleeve(conn, xirr_user["uid"], xirr_user["account_id"], qty=500.0)
        resp = await api.get("/api/v1/portfolio/xirr", headers=xirr_user["headers"])
        data = resp.json()
        assert data["consolidated"] is not None
        assert data["by_category"]["Cripto"] is not None
        assert abs(data["consolidated"] - data["by_category"]["Cripto"]) < 1e-6
        assert data["consolidated"] < 0  # perda (500 vs 1000)

    @pytest.mark.asyncio
    async def test_no_crypto_no_cripto_category(
        self, api: AsyncClient, xirr_user: dict
    ) -> None:
        """Sem dado cripto → não inventa a categoria Cripto no XIRR."""
        resp = await api.get("/api/v1/portfolio/xirr", headers=xirr_user["headers"])
        assert "Cripto" not in resp.json()["by_category"]
