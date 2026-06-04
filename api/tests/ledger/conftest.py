"""Fixtures do Ledger: cliente httpx (ASGI) + headers autenticados.

Reusa o pool top-level (tests/conftest.py). O app não roda lifespan sob
ASGITransport; o pool global é inicializado pela fixture `pool`, da qual
`auth_headers` depende — então as rotas que usam get_db() funcionam.
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "ledger-test-password"


@pytest_asyncio.fixture
async def api(pool: object) -> AsyncIterator[httpx.AsyncClient]:
    # Depende de `pool` p/ inicializar o pool global (o app não roda lifespan sob
    # ASGITransport); assim get_db() funciona mesmo nas rotas sem auth.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(pool: object) -> AsyncIterator[dict[str, str]]:
    email = f"ledger-{uuid.uuid4().hex[:8]}@example.com"
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
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
