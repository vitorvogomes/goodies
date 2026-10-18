"""Status do mês (AD-8 — Story 2.1).

Engines que escrevem num mês (`ingest`, `categorize`, reaplicação, desfazer) chamam `mark_dirty`; os
avisos leem `status`/`is_closed`. Até o fechamento existir (Épico 5) vale a implementação padrão
"todos os meses abertos"; `closing` registra a real em `main.py`.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Protocol

MonthState = Literal["aberto", "fechado", "ajuste"]


class MonthStatusPort(Protocol):
    async def status(self, conn: Any, month: date) -> MonthState: ...

    async def is_closed(self, conn: Any, month: date) -> bool: ...

    async def mark_dirty(self, conn: Any, month: date) -> None: ...


class AllMonthsOpen:
    async def status(self, conn: Any, month: date) -> MonthState:
        return "aberto"

    async def is_closed(self, conn: Any, month: date) -> bool:
        return False

    async def mark_dirty(self, conn: Any, month: date) -> None:
        return None


_port: MonthStatusPort = AllMonthsOpen()


def register_month_status(port: MonthStatusPort) -> None:
    global _port
    _port = port


def month_status() -> MonthStatusPort:
    return _port
