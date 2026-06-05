"""Fixtures for portfolio tests: client + auth."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "portfolio-test-password"


@pytest_asyncio.fixture
async def api(pool: object) -> AsyncIterator[httpx.AsyncClient]:
    """AsyncClient with ASGI transport for FastAPI app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(pool: object) -> AsyncIterator[dict[str, str]]:
    """Create test user and return auth headers with bearer token."""
    email = f"portfolio-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            hash_password(_PASSWORD),
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
        )
    token = resp.json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        await conn.execute("DELETE FROM asset_operations WHERE user_id = $1", uid)
        # asset_prices is global (keyed by ticker, no user_id) — wipe between tests
        # to keep per-user isolation. Sequential test execution makes this safe.
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
