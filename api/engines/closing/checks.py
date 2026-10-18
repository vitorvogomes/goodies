"""Registro de precondições do fechamento (AD-8 — Story 5.3): cada engine registra em `main.py`
verificações `bloqueia` ou `confirma` para um mês; `closing` só as junta."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date

import asyncpg

from engines.common.dates import month_label, today_brt

from .models import CloseCheck

# As engines de baixo não importam `closing`: devolvem {"code", "kind", "message"}.
CloseCheckFn = Callable[[asyncpg.Connection, date], Awaitable[list[dict[str, str]]]]
_checks: list[CloseCheckFn] = []

label = month_label


def register_close_check(check: CloseCheckFn) -> None:
    if check not in _checks:
        _checks.append(check)


async def month_in_progress(conn: asyncpg.Connection, month: date) -> list[CloseCheck]:
    """O mês só fecha depois de terminar."""
    if month >= today_brt().replace(day=1):
        return [
            CloseCheck(
                code="mes_em_curso", kind="bloqueia", message=f"{label(month)} ainda não terminou."
            )
        ]
    return []


async def run_checks(conn: asyncpg.Connection, month: date) -> list[CloseCheck]:
    found = await month_in_progress(conn, month)
    for check in _checks:
        found.extend(CloseCheck(**c) for c in await check(conn, month))
    return found
