"""Upsert do usuário admin (dono único) — `seed_admin` e bootstrap da subida (ADR-018).

A senha chega por variável de ambiente e só o hash bcrypt vai ao banco; nada aqui loga senha.
"""

from __future__ import annotations

import asyncpg

from auth.security import hash_password


async def upsert_admin(dsn: str, email: str, password: str) -> None:
    """Cria o admin ou troca a senha dele (idempotente por e-mail)."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO users (email, password_hash)
            VALUES ($1, $2)
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            email,
            hash_password(password),
        )
    finally:
        await conn.close()
