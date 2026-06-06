"""Fixtures dos testes do Wallet Engine (m4)."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio

from auth.security import hash_password

_PASSWORD = "wallet-test-password"


@pytest_asyncio.fixture
async def wallet_user(pool: Any) -> AsyncIterator[dict[str, Any]]:
    """Usuário de teste; yields {user_id}. Limpa wallet_positions + usuário no fim."""
    email = f"wallet-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = str(
            await conn.fetchval(
                "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
                email,
                hash_password(_PASSWORD),
            )
        )
    yield {"user_id": uid}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM users WHERE id = $1", uid)
