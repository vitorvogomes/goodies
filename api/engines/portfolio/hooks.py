"""Derivações do portfolio sobre o ledger (AD-6): registradas em `main.py`.

Transação que muda (import, categorize, reaplicação, desfazer) pode mexer em aporte, resgate ou no
bloco cripto, que alimentam o XIRR consolidado: refaz as operações de caixinha/CDB dessas transações
(Story 3.5) e invalida o cache do dono (ADR-008, AD-5).
"""

from __future__ import annotations

import asyncpg

from engines.common.cache import invalidate_xirr_cache
from engines.common.owner import get_owner_id
from engines.portfolio.caixinhas import derive_caixinha_ops


async def on_transactions_changed(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    owner = await get_owner_id(conn)
    await derive_caixinha_ops(conn, owner, transaction_ids)
    await invalidate_xirr_cache(owner)


async def on_batch_applied(conn: asyncpg.Connection, batch_id: str) -> None:
    """Lote aplicado (AD-5): mesma derivação, uma vez por lote, na transação do `apply`."""
    ids = [
        str(r["id"])
        for r in await conn.fetch("SELECT id FROM transactions WHERE batch_id = $1::uuid", batch_id)
    ]
    owner = await get_owner_id(conn)
    if ids:
        await derive_caixinha_ops(conn, owner, ids)
    await invalidate_xirr_cache(owner)


async def on_batch_undo(conn: asyncpg.Connection, batch_id: str) -> None:
    """Antes do `undo` dos adapters: sai a operação derivada das transações do lote (a FK
    `transaction_id` é RESTRICT); a protegida fica e trava o desfazer."""
    await conn.execute(
        "DELETE FROM asset_operations o USING transactions t "
        "WHERE o.transaction_id = t.id AND t.batch_id = $1::uuid AND NOT o.protected",
        batch_id,
    )
    await invalidate_xirr_cache(await get_owner_id(conn))


async def count_derived_for_undo(conn: asyncpg.Connection, batch_id: str) -> dict[str, int]:
    """Prévia do desfazer: operações derivadas (não protegidas) das transações do lote."""
    n = await conn.fetchval(
        "SELECT count(*) FROM asset_operations o JOIN transactions t ON t.id = o.transaction_id "
        "WHERE t.batch_id = $1::uuid AND NOT o.protected",
        batch_id,
    )
    return {"operations": int(n)}


async def on_transactions_deleting(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    """Transação apagada leva junto a operação derivada dela; a protegida (curadoria) fica e a FK
    RESTRICT recusa o apagar."""
    await conn.execute(
        "DELETE FROM asset_operations WHERE transaction_id = ANY($1::uuid[]) AND NOT protected",
        transaction_ids,
    )
    await invalidate_xirr_cache(await get_owner_id(conn))
