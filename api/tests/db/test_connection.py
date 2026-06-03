"""STORY-00-03 — pool asyncpg + schema users.

Testa contra o Postgres local do docker-compose. O fixture `pool` e a aplicação
das migrations vivem em conftest.py.
"""

import uuid


async def test_pool_executes_select_one(pool):
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1


async def test_users_insert_and_select(pool):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            "bcrypt$dummy",
        )
        row = await conn.fetchrow(
            "SELECT id, email, password_hash, created_at FROM users WHERE id = $1",
            uid,
        )
        await conn.execute("DELETE FROM users WHERE id = $1", uid)  # cleanup

    assert row is not None
    assert row["email"] == email
    assert row["password_hash"] == "bcrypt$dummy"
    assert row["created_at"] is not None
