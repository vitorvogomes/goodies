"""Dono único dos dados (AD-18 — Story 2.1): o app é de um usuário só; tabelas novas gravam
`user_id` NOT NULL com este id."""
from __future__ import annotations

import asyncpg


class NoOwnerError(RuntimeError):
    """Banco sem usuário cadastrado."""


async def get_owner_id(conn: asyncpg.Connection) -> str:
    owner = await conn.fetchval("SELECT id FROM users ORDER BY created_at, id LIMIT 1")
    if owner is None:
        raise NoOwnerError("nenhum usuário cadastrado (rode scripts.ops.seed_admin)")
    return str(owner)
