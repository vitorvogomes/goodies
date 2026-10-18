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
    WHERE (c.key = ANY($1::text[])
           OR ($4 AND c.key IN (SELECT p.pair_key FROM categories p
                                WHERE p.key = ANY($1::text[]) AND p.pair_key IS NOT NULL)))
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
    with_pairs: bool = False,
) -> list[asyncpg.Record]:
    """Transações das subcategorias `keys` (opcional: só um `kind`; descrição com algum dos termos;
    `with_pairs` inclui o par investimento ↔ resgate do trilho — Story 2.6), por data: date, amount,
    external_id, description, category_key, category_name."""
    rows: list[asyncpg.Record] = await conn.fetch(
        _BY_KEYS, list(keys), kind, list(description_any), with_pairs
    )
    return rows


ACTIVE_RULES = """
    SELECT r.id, r.pattern, r.direction, r.category_id, r.created_at, c.name AS category_name,
           g.kind
    FROM category_rules r
    JOIN categories c ON c.id = r.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE r.is_active AND c.is_active
"""

CATEGORY_INFO = """
    SELECT c.id, c.name, c.key, c.role, g.kind
    FROM categories c JOIN category_groups g ON g.id = c.group_id
    WHERE c.id = ANY($1::uuid[])
"""

CATEGORY_BY_KEY = "SELECT id FROM categories WHERE key = $1"

TX_STATE = """
    SELECT id, category_id, category_source, review_status, date
    FROM transactions WHERE id = ANY($1::uuid[]) FOR UPDATE
"""

APPLY_CATEGORY = """
    UPDATE transactions SET
      category_id = $2, category = $3, kind = $4, category_source = $5, category_rule_id = $6,
      review_status = COALESCE($7, review_status)
    WHERE id = $1
"""

INSERT_EVENT = """
    INSERT INTO categorization_events
      (transaction_id, before_category_id, after_category_id, source, cause, batch_id, rule_id)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
"""


async def active_rules(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(ACTIVE_RULES)
    return rows


async def category_id_by_key(conn: asyncpg.Connection, key: str) -> str:
    value = await conn.fetchval(CATEGORY_BY_KEY, key)
    if value is None:
        raise LookupError(f"categoria de sistema ausente: {key}")
    return str(value)


MONTH_MOVEMENTS = """
    SELECT date_trunc('month', t.date)::date AS month, t.kind, c.role, sum(t.amount) AS amount
    FROM transactions t JOIN categories c ON c.id = t.category_id
    WHERE ($1::date[] IS NULL OR date_trunc('month', t.date)::date = ANY($1::date[]))
    GROUP BY 1, 2, 3
"""


async def month_movements(
    conn: asyncpg.Connection, months: Sequence[object] | None = None
) -> list[asyncpg.Record]:
    """Transações agregadas por (mês, kind, role) — os termos de AD-7 são somas, então a agregação
    não muda o resultado das funções de `ledger/calc`."""
    rows: list[asyncpg.Record] = await conn.fetch(
        MONTH_MOVEMENTS, list(months) if months is not None else None
    )
    return rows
