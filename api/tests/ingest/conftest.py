"""Cliente ASGI, login e conta de teste do ledger, reusados pela engine ingest; conta com número
(OFX)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio

from tests.ledger.conftest import account, api, auth_headers  # noqa: F401


@pytest_asyncio.fixture
async def ofx_account(pool: Any) -> AsyncIterator[tuple[str, str]]:
    number = str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, 'bank', $2) "
            "RETURNING id",
            f"ofx-{number}",
            number,
        )
    yield str(acc), number
    async with pool.acquire() as conn:
        batches = [
            r["batch_id"]
            for r in await conn.fetch(
                "SELECT DISTINCT batch_id FROM transactions WHERE account_id = $1", acc
            )
        ]
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM import_batches WHERE id = ANY($1::uuid[])", batches)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
