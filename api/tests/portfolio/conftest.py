"""Fixtures for portfolio tests: client + auth."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "portfolio-test-password"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _create_user_and_login(pool: Any) -> tuple[str, dict[str, str]]:
    """Create a fresh test user and return (user_id, auth headers)."""
    email = f"portfolio-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            hash_password(_PASSWORD),
        )
    async with _client() as client:
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    token = resp.json()["access_token"]
    return str(uid), {"Authorization": f"Bearer {token}"}


async def _cleanup_user(pool: Any, uid: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM asset_operations WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM portfolio_targets WHERE user_id = $1", uid)
        # carteiras cripto (m4): o sleeve folda wallet/defi nas posições/alocação — limpar
        # p/ não vazar valor cripto entre testes (user-scoped).
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM crypto_cost_basis WHERE user_id = $1", uid)
        # asset_prices is global (keyed by ticker, no user_id) — wipe between tests
        # to keep per-user isolation. Sequential test execution makes this safe.
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


DEFAULT_TARGETS = (
    ("Ações Nacionais", 10.0),
    ("Aposentadoria", 12.5),
    ("Cripto", 5.0),
    ("ETFs", 12.5),
    ("FIIs", 10.0),
    ("Renda Fixa", 50.0),
)


@pytest_asyncio.fixture
async def api(pool: object) -> AsyncIterator[httpx.AsyncClient]:
    """AsyncClient with ASGI transport for FastAPI app."""
    async with _client() as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(pool: Any) -> AsyncIterator[dict[str, str]]:
    """Create test user and return auth headers with bearer token."""
    uid, headers = await _create_user_and_login(pool)
    yield headers
    await _cleanup_user(pool, uid)


@pytest_asyncio.fixture
async def portfolio_user(pool: Any) -> AsyncIterator[dict[str, Any]]:
    """Test user with portfolio targets seeded; yields {headers, user_id}."""
    uid, headers = await _create_user_and_login(pool)
    async with pool.acquire() as conn:  # as metas padrão (as da revisão 0043)
        await conn.executemany(
            "INSERT INTO portfolio_targets (user_id, category, target_pct) VALUES ($1, $2, $3)",
            [(uid, category, pct) for category, pct in DEFAULT_TARGETS],
        )
    yield {"headers": headers, "user_id": uid}
    await _cleanup_user(pool, uid)


async def set_price(symbol: str, price: float) -> None:
    """Preço de teste pelo chokepoint do market (a rota manual só aceita ativo sem fonte de
    mercado desde a Story 10.2)."""
    import asyncpg

    from engines.market import service as market_service
    from tests.conftest import TEST_DSN

    conn = await asyncpg.connect(TEST_DSN)
    try:
        await market_service.upsert_price(conn, symbol, price)
        await market_service.invalidate_price_cache(symbol)
    finally:
        await conn.close()
