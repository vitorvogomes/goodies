"""Derivações do portfolio sobre o ledger (AD-6): registradas em `main.py`.

Transação que muda (import, categorize, reaplicação, desfazer) pode mexer em aporte, resgate ou no
bloco cripto, que alimentam o XIRR consolidado: invalida o cache do dono (ADR-008, AD-5).
"""

from __future__ import annotations

import asyncpg

from engines.common.cache import invalidate_xirr_cache
from engines.common.owner import get_owner_id


async def on_transactions_changed(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    await invalidate_xirr_cache(await get_owner_id(conn))
