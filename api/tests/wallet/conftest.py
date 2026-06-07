"""Fixtures dos testes do Wallet Engine (m4)."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "wallet-test-password"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def api(pool: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as client:
        yield client


@pytest_asyncio.fixture
async def wallet_user(pool: Any) -> AsyncIterator[dict[str, Any]]:
    """Usuário autenticado; yields {user_id, headers}. Limpa wallet/defi + usuário no fim."""
    email = f"wallet-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = str(
            await conn.fetchval(
                "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
                email,
                hash_password(_PASSWORD),
            )
        )
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
        )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    yield {"user_id": uid, "headers": headers}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
