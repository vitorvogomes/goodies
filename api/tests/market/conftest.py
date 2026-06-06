"""Fixtures dos testes do Market Engine.

- `clean_market_prices` (autouse): os testes de fallback gravam em `asset_prices`
  (tabela global). Usam tickers com prefixo `MKT_` e esta fixture os limpa entre testes.
- `api` + `portfolio_user`: cliente ASGI + usuário autenticado (auth dos endpoints).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "market-test-password"


@pytest_asyncio.fixture(autouse=True)
async def clean_market_prices(pool: Any) -> AsyncIterator[None]:
    async def _wipe() -> None:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_prices WHERE ticker LIKE 'MKT\\_%'")

    await _wipe()
    yield
    await _wipe()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest_asyncio.fixture
async def api(pool: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as client:
        yield client


@pytest_asyncio.fixture
async def portfolio_user(pool: Any) -> AsyncIterator[dict[str, Any]]:
    """Usuário autenticado: yields {headers, user_id}. Limpa ops/preços/usuário no fim."""
    email = f"market-{uuid.uuid4().hex[:8]}@example.com"
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
    yield {"headers": headers, "user_id": uid}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM asset_operations WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
