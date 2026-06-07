"""Helpers compartilhados dos scripts operacionais (resolução de usuário).

Centraliza o `SELECT id FROM users ... LIMIT 1` que estava duplicado em ~7 scripts e
adiciona suporte a `--user <id|email>` (app é single-user, mas o default deixa de ser
o "primeiro usuário" hardcoded espalhado).
"""
from __future__ import annotations

import sys

import asyncpg


def user_arg(argv: list[str] | None = None) -> str | None:
    """Lê `--user <id|email>` de argv. None = default (1º usuário, app single-user)."""
    args = argv if argv is not None else sys.argv
    if "--user" in args:
        i = args.index("--user")
        if i + 1 < len(args):
            return args[i + 1]
    return None


async def resolve_owner(
    conn: asyncpg.Connection, user: str | None = None
) -> asyncpg.Record | None:
    """Linha (id, email) do dono: explícito (`--user` = uuid OU email) ou o 1º usuário.

    Substitui o `SELECT id FROM users ... LIMIT 1` cru duplicado nos scripts. None se
    não houver usuário (ou o `--user` não casar).
    """
    if user:
        return await conn.fetchrow(
            "SELECT id, email FROM users WHERE id::text = $1 OR email = $1", user
        )
    return await conn.fetchrow(
        "SELECT id, email FROM users ORDER BY created_at LIMIT 1"
    )
