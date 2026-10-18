"""SQL público do ledger (AD-2/AD-3 — Story 2.3).

Outras engines leem transações por `categories.key` (imutável) daqui, nunca pelo nome da categoria
nem com SQL próprio sobre `transactions`.
"""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg

_BY_KEYS = """
    SELECT t.id, t.date, t.amount, t.external_id, t.description, c.key AS category_key,
           c.name AS category_name
    FROM transactions t JOIN categories c ON c.id = t.category_id
    WHERE (c.key = ANY($1::text[])
           OR ($4 AND c.key IN (SELECT p.pair_key FROM categories p
                                WHERE p.key = ANY($1::text[]) AND p.pair_key IS NOT NULL)))
      AND ($2::text IS NULL OR t.kind = $2)
      AND (cardinality($3::text[]) = 0
           OR EXISTS (SELECT 1 FROM unnest($3::text[]) d WHERE t.description ILIKE '%' || d || '%'))
      AND ($5::uuid[] IS NULL OR t.id = ANY($5::uuid[]))
    ORDER BY t.date, t.id
"""


async def transactions_by_category_keys(
    conn: asyncpg.Connection,
    keys: Sequence[str],
    *,
    kind: str | None = None,
    description_any: Sequence[str] = (),
    with_pairs: bool = False,
    ids: Sequence[str] | None = None,
) -> list[asyncpg.Record]:
    """Transações das subcategorias `keys` (opcional: só um `kind`; descrição com algum dos termos;
    `with_pairs` inclui o par investimento ↔ resgate do trilho — Story 2.6; só os `ids` dados), por
    data: id, date, amount, external_id, description, category_key, category_name."""
    rows: list[asyncpg.Record] = await conn.fetch(
        _BY_KEYS,
        list(keys),
        kind,
        list(description_any),
        with_pairs,
        list(ids) if ids is not None else None,
    )
    return rows


ACTIVE_RULES = """
    SELECT r.id, r.pattern, r.direction, r.category_id, r.created_at, c.name AS category_name,
           g.kind
    FROM category_rules r
    JOIN categories c ON c.id = r.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE r.is_active AND c.is_active AND g.is_active
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


TX_COLUMNS = """
    t.id, t.date, t.description, t.amount, t.kind, t.category_id, c.name AS category_name,
    c.key AS category_key, g.name AS group_name, t.category_source, t.review_status, t.payer,
    t.account_id, a.name AS account_name, t.source, t.batch_id, r.pattern AS rule_pattern,
    (SELECT f.file_name FROM import_batch_files f WHERE f.batch_id = t.batch_id
     ORDER BY f.created_at LIMIT 1) AS file_name
"""
TX_FROM = """
    FROM transactions t
    JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    JOIN accounts a ON a.id = t.account_id
    LEFT JOIN category_rules r ON r.id = t.category_rule_id
"""


async def transactions_page(
    conn: asyncpg.Connection, start: object, end: object, limit: int, offset: int
) -> tuple[list[asyncpg.Record], int]:
    rows: list[asyncpg.Record] = await conn.fetch(
        f"SELECT {TX_COLUMNS} {TX_FROM} WHERE t.date >= $1 AND t.date < $2 "
        "ORDER BY t.date DESC, t.created_at DESC, t.id LIMIT $3 OFFSET $4",
        start,
        end,
        limit,
        offset,
    )
    total = await conn.fetchval(
        "SELECT count(*) FROM transactions t WHERE t.date >= $1 AND t.date < $2", start, end
    )
    return rows, int(total)


async def transaction_row(conn: asyncpg.Connection, tx_id: str) -> asyncpg.Record | None:
    row: asyncpg.Record | None = await conn.fetchrow(
        f"SELECT {TX_COLUMNS} {TX_FROM} WHERE t.id = $1", tx_id
    )
    return row


async def category_options(
    conn: asyncpg.Connection, include_archived: bool
) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(
        """
        SELECT c.id, c.key, c.name, c.role, c.is_active, g.key AS group_key,
               g.name AS group_name, g.kind
        FROM categories c JOIN category_groups g ON g.id = c.group_id
        WHERE NOT g.is_system AND ($1 OR (c.is_active AND g.is_active))
        ORDER BY g.kind, g.name, c.name
        """,
        include_archived,
    )
    return rows


async def category_exists(conn: asyncpg.Connection, category_id: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM categories WHERE id = $1::uuid)", category_id
        )
    )


async def tx_source(conn: asyncpg.Connection, tx_id: str) -> asyncpg.Record | None:
    row: asyncpg.Record | None = await conn.fetchrow(
        "SELECT id, source, date FROM transactions WHERE id = $1::uuid FOR UPDATE", tx_id
    )
    return row


TREE_GROUPS = """
    SELECT g.id, g.key, g.name, g.kind, g.is_active, g.is_system FROM category_groups g
    WHERE NOT g.is_system AND ($1 OR g.is_active) ORDER BY g.kind, g.name
"""
TREE_CATEGORIES = """
    SELECT c.id, c.key, c.name, c.group_id, g.kind, c.role, c.is_active,
           c.key LIKE 'sistema:%' AS is_system,
           (SELECT count(*) FROM transactions t WHERE t.category_id = c.id) AS transaction_count
    FROM categories c JOIN category_groups g ON g.id = c.group_id
    WHERE NOT g.is_system AND ($1 OR (c.is_active AND g.is_active))
    ORDER BY c.name
"""
CATEGORY_ROW = """
    SELECT c.id, c.key, c.name, c.group_id, g.kind, c.role, c.is_active,
           c.key LIKE 'sistema:%' AS is_system,
           (SELECT count(*) FROM transactions t WHERE t.category_id = c.id) AS transaction_count
    FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE c.id = $1::uuid
"""
# Renome (Story 2.9): o texto legado acompanha o nome — exceção documentada a "só categorize()
# escreve categoria": não muda a subcategoria de nenhuma transação, só o rótulo (sem evento).
RENAME_TEXT_COLUMNS = (
    "UPDATE transactions SET category = $2 WHERE category_id = $1::uuid",
    "UPDATE fixed_costs SET category = $2 WHERE category_id = $1::uuid",
)


RULES_LIST = """
    SELECT r.id, r.pattern, r.direction, r.category_id, r.is_active, r.origin, r.created_at,
           g.name || ' › ' || c.name AS category_label
    FROM category_rules r JOIN categories c ON c.id = r.category_id
    JOIN category_groups g ON g.id = c.group_id
    ORDER BY r.is_active DESC, lower(r.pattern), r.direction
"""
RULE_MATCHES = """
    SELECT t.id, t.date, t.description, t.amount,
           CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END AS category_label,
           count(*) OVER () AS total
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE position(lower($1) IN lower(coalesce(t.description, ''))) > 0
      AND ($2 = 'ambos' OR ($2 = 'entrada' AND t.amount > 0) OR ($2 = 'saida' AND t.amount < 0))
    ORDER BY t.date DESC LIMIT 20
"""
TX_IN_RANGE = """
    SELECT t.id, t.date, t.description, t.amount, t.category_id, t.category_source,
           CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END AS category_label
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE t.date >= $1 AND t.date < $2 ORDER BY t.date, t.id
"""
CATEGORY_LABELS = """
    SELECT c.id, CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END AS label
    FROM categories c JOIN category_groups g ON g.id = c.group_id
"""
CATEGORY_HAS_HISTORY = """
    SELECT EXISTS (SELECT 1 FROM categorization_events
                   WHERE before_category_id = $1::uuid OR after_category_id = $1::uuid)
"""
CONSUMPTION_BY_CATEGORY = """
    SELECT date_trunc('month', t.date)::date AS month, c.id AS category_id,
           g.name || ' › ' || c.name AS label, SUM(-t.amount) AS total
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE c.role = 'consumo'
      AND t.date >= (date_trunc('month', $1::date) - interval '3 months')
      AND t.date <  (date_trunc('month', $1::date) + interval '1 month')
    GROUP BY 1, 2, 3
"""
CONFIRMED_HISTORY = """
    SELECT t.description, t.category_id, t.amount > 0 AS positive
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE t.review_status = 'confirmed' AND NOT g.is_system AND c.is_active
      AND coalesce(t.description, '') <> ''
    ORDER BY t.date DESC, t.created_at DESC
"""
REVIEW_ITEMS = """
    SELECT t.id, t.date, t.description, t.amount, a.name AS account_name, t.category_id,
           t.category_source, t.category_rule_id, g.is_system, g.kind AS category_kind,
           CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END AS category_label,
           r.pattern AS rule_pattern
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    JOIN accounts a ON a.id = t.account_id
    LEFT JOIN category_rules r ON r.id = t.category_rule_id
    WHERE t.review_status = 'pending' AND ($1::uuid IS NULL OR t.batch_id = $1::uuid)
      AND ($2::date IS NULL OR date_trunc('month', t.date)::date = $2::date)
    ORDER BY t.date, t.id
"""
PENDING_COUNT = """
    SELECT count(*) FROM transactions
    WHERE review_status = 'pending' AND ($1::uuid IS NULL OR batch_id = $1::uuid)
"""
REVIEW_STATE = """
    SELECT t.id, t.category_id, t.category_source, t.category_rule_id
    FROM transactions t WHERE t.id = ANY($1::uuid[])
"""
SYSTEM_CATEGORIES = """
    SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id
    WHERE g.is_system AND c.id = ANY($1::uuid[])
"""
RULE_TARGETS = """
    SELECT t.id, t.category_id, t.description, t.amount FROM transactions t
    WHERE position(lower($1) IN lower(coalesce(t.description, ''))) > 0
      AND ($2 = 'ambos' OR ($2 = 'entrada' AND t.amount > 0) OR ($2 = 'saida' AND t.amount < 0))
      AND t.category_source <> 'manual' AND t.category_id <> $3::uuid
      AND ($4::uuid IS NULL OR t.id <> $4::uuid)
"""
UPSERT_RULE = """
    INSERT INTO category_rules (pattern, direction, category_id, origin, created_in_batch)
    VALUES ($1, $2, $3::uuid, $4, $5::uuid)
    ON CONFLICT (pattern, direction, category_id) DO UPDATE SET is_active = true
    RETURNING id
"""
CATEGORY_LABEL_BY_ID = """
    SELECT CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END
    FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE c.id = $1::uuid
"""
PF_ACCOUNT = (
    "SELECT id, account_number FROM accounts WHERE holder = 'pf' ORDER BY created_at LIMIT 1"
)
REPORTED_BALANCES = """
    SELECT as_of, balance FROM account_balances WHERE account_id = $1 ORDER BY as_of
"""
ACCOUNT_MOVEMENTS = "SELECT date, amount FROM transactions WHERE account_id = $1 ORDER BY date"
INTERVAL_TRANSACTIONS = """
    SELECT t.id, t.date, t.description, t.amount,
           CASE WHEN g.is_system THEN c.name ELSE g.name || ' › ' || c.name END AS category_label
    FROM transactions t JOIN categories c ON c.id = t.category_id
    JOIN category_groups g ON g.id = c.group_id
    WHERE t.account_id = $1 AND t.date > $2 AND t.date <= $3
"""
UNDO_COUNTS = """
    SELECT
      (SELECT count(*) FROM transactions WHERE batch_id = $1::uuid) AS transactions,
      (SELECT count(*) FROM categorization_events e JOIN transactions t ON t.id = e.transaction_id
        WHERE t.batch_id = $1::uuid) AS categorizations,
      (SELECT count(*) FROM category_rules WHERE created_in_batch = $1::uuid) AS rules,
      (SELECT count(*) FROM account_balances WHERE batch_id = $1::uuid) AS balances
"""
RULED_OUTSIDE_BATCH = """
    SELECT t.id, t.description, t.amount FROM transactions t
    JOIN category_rules r ON r.id = t.category_rule_id
    WHERE r.created_in_batch = $1::uuid AND t.batch_id IS DISTINCT FROM $1::uuid
"""
ANCHORS_IN_BATCH = """
    SELECT DISTINCT a.id AS account_id FROM accounts a
    JOIN account_balances b ON b.account_id = a.id AND b.as_of = a.opening_balance_date
    WHERE b.batch_id = $1::uuid
"""
HISTORY_VERSION = """
    SELECT (SELECT count(*) FROM transactions WHERE review_status = 'confirmed'),
           (SELECT max(created_at) FROM categorization_events)
"""
LAST_DATE_IN_MONTH = """
    SELECT max(date) FROM transactions
    WHERE date >= $1::date AND date < ($1::date + interval '1 month')
"""
ANCHORED_ACCOUNTS = "SELECT id, opening_balance FROM accounts WHERE opening_balance IS NOT NULL"
INCOME_BY_PAYER = """
    SELECT coalesce(t.payer, 'sem pagador') AS payer, sum(t.amount) AS total
    FROM transactions t
    WHERE t.kind = 'income' AND t.date >= $1::date AND t.date < ($1::date + interval '1 month')
    GROUP BY 1
"""
EXPENSES_BY_CATEGORY = """
    SELECT t.category_id::text AS category_id, -sum(t.amount) AS total
    FROM transactions t
    WHERE t.kind = 'expense' AND t.date >= $1::date AND t.date < ($1::date + interval '1 month')
    GROUP BY 1
"""
