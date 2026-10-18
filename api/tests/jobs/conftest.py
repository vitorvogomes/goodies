"""Fixtures dos testes de jobs: cliente httpx (ASGI) + headers autenticados."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "jobs-test-password"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def api(pool: object) -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(pool: Any) -> AsyncIterator[dict[str, str]]:
    email = f"jobs-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            hash_password(_PASSWORD),
        )
    async with _client() as client:
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    token = resp.json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
