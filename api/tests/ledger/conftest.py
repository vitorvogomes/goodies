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


@pytest_asyncio.fixture(autouse=True)
async def _clean_fixed_costs(pool: object) -> AsyncIterator[None]:
    """Remove custos fixos criados no teste (fixed_costs é global). Teardown roda
    mesmo se um assert falhar, evitando poluir projeção/alertas de outros testes."""
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        before = [r["id"] for r in await conn.fetch("SELECT id FROM fixed_costs")]
    yield
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        if before:
            await conn.execute("DELETE FROM fixed_costs WHERE id <> ALL($1::uuid[])", before)
        else:
            await conn.execute("DELETE FROM fixed_costs")


@pytest_asyncio.fixture(autouse=True)
async def _clean_accounts(pool: object) -> AsyncIterator[None]:
    """Remove contas (e suas transações) criadas durante o teste. Defesa contra
    vazamento de accounts mesmo se um teste esquecer o cleanup (ex.: STORY-01-02)."""
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        before = [r["id"] for r in await conn.fetch("SELECT id FROM accounts")]
    yield
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        if before:
            await conn.execute(
                "DELETE FROM transactions WHERE account_id <> ALL($1::uuid[])", before
            )
            await conn.execute("DELETE FROM accounts WHERE id <> ALL($1::uuid[])", before)
        else:
            await conn.execute("DELETE FROM transactions")
            await conn.execute("DELETE FROM accounts")


@pytest_asyncio.fixture
async def account(pool: object) -> AsyncIterator[str]:
    """Cria uma conta de teste; limpa transações associadas + a conta ao fim."""
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, $2) RETURNING id",
            f"acc-{uuid.uuid4().hex[:8]}",
            "bank",
        )
    yield str(acc)
    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
