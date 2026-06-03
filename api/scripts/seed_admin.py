"""Seed do usuário admin (Vitor) — STORY-00-03.

Lê ADMIN_EMAIL e ADMIN_PASSWORD do ambiente — NÃO embute senha no repo
(security.md / ADR-006). Upsert idempotente com hash bcrypt (passlib).

Uso (a partir de api/):
    ADMIN_EMAIL=... ADMIN_PASSWORD=... .venv/bin/python -m scripts.seed_admin
"""

import asyncio
import os

import asyncpg
from passlib.context import CryptContext

from config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_admin() -> None:
    email = os.environ["ADMIN_EMAIL"]
    password = os.environ["ADMIN_PASSWORD"]
    password_hash: str = _pwd_context.hash(password)

    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(
            """
            INSERT INTO users (email, password_hash)
            VALUES ($1, $2)
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            email,
            password_hash,
        )
    finally:
        await conn.close()
    print(f"admin seeded: {email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
