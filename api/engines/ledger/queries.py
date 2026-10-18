"""SQL público do ledger (AD-2/AD-3 — Story 2.3).

Outras engines leem transações por `categories.key` (imutável) daqui, nunca pelo nome da categoria
nem com SQL próprio sobre `transactions`.
"""
from __future__ import annotations

from collections.abc import Sequence

import asyncpg

_BY_KEYS = """
    SELECT t.date, t.amount, t.external_id, t.description, c.key AS category_key,
           c.name AS category_name
    FROM transactions t JOIN categories c ON c.id = t.category_id
    WHERE c.key = ANY($1::text[])
      AND ($2::text IS NULL OR t.kind = $2)
      AND (cardinality($3::text[]) = 0
           OR EXISTS (SELECT 1 FROM unnest($3::text[]) d WHERE t.description ILIKE '%' || d || '%'))
    ORDER BY t.date, t.id
"""


async def transactions_by_category_keys(
    conn: asyncpg.Connection,
    keys: Sequence[str],
    *,
    kind: str | None = None,
    description_any: Sequence[str] = (),
) -> list[asyncpg.Record]:
    """Transações das subcategorias `keys` (opcional: só um `kind`; descrição com algum dos termos),
    por data: date, amount, external_id, description, category_key, category_name."""
    rows: list[asyncpg.Record] = await conn.fetch(
        _BY_KEYS, list(keys), kind, list(description_any)
    )
    return rows
