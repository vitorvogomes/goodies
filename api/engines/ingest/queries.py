"""SQL da engine ingest (dona de `import_batches` e `import_batch_files` — AD-3)."""

from __future__ import annotations

from typing import Any

import asyncpg

INSERT_BATCH = """
    INSERT INTO import_batches (user_id, status, applied_at)
    VALUES ($1, $2, CASE WHEN $2 IN ('applied', 'legacy') THEN now() END)
    RETURNING id
"""

INSERT_FILE = """
    INSERT INTO import_batch_files
      (batch_id, user_id, source, account_id, broker, file_name, file_hash,
       period_start, period_end, reported_balance, reported_balance_date)
    VALUES ($1, $2, $3, $4::uuid, $5, $6, $7, $8, $9, $10, $11)
"""

SELECT_BATCHES = """
    SELECT id, status, created_at, applied_at FROM import_batches
    WHERE user_id = $1 ORDER BY created_at DESC, id LIMIT $2
"""

SELECT_FILES = """
    SELECT id, batch_id, source, account_id, broker, file_name, file_hash, period_start, period_end,
           reported_balance, reported_balance_date
    FROM import_batch_files WHERE batch_id = ANY($1::uuid[]) ORDER BY created_at, id
"""


async def insert_batch(conn: asyncpg.Connection, user_id: str, status: str) -> str:
    return str(await conn.fetchval(INSERT_BATCH, user_id, status))


async def insert_file(
    conn: asyncpg.Connection, batch_id: str, user_id: str, f: dict[str, Any]
) -> None:
    await conn.execute(
        INSERT_FILE,
        batch_id,
        user_id,
        f["source"],
        f.get("account_id"),
        f.get("broker"),
        f.get("file_name"),
        f.get("file_hash"),
        f.get("period_start"),
        f.get("period_end"),
        f.get("reported_balance"),
        f.get("reported_balance_date"),
    )


async def select_batches(
    conn: asyncpg.Connection, user_id: str, limit: int
) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(SELECT_BATCHES, user_id, limit)
    return rows


async def select_files(conn: asyncpg.Connection, batch_ids: list[str]) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(SELECT_FILES, batch_ids)
    return rows


# ---- prévia → confirmação (Story 3.3) ----

INSERT_STAGED = """
    INSERT INTO import_batches (user_id, status, plan, plan_hash, expires_at)
    VALUES ($1, 'staged', $2::jsonb, $3, now() + interval '24 hours')
    RETURNING id, expires_at
"""
STAGED_FOR_UPDATE = """
    SELECT id, status, plan, plan_hash, expires_at <= now() AS expired
    FROM import_batches WHERE id = $1::uuid FOR UPDATE
"""
MARK_APPLIED = """
    UPDATE import_batches SET status = 'applied', applied_at = now(), expires_at = NULL
    WHERE id = $1::uuid
"""
DROP_EXPIRED = "DELETE FROM import_batches WHERE status = 'staged' AND expires_at <= now()"
APPLIED_HASHES = """
    SELECT DISTINCT f.file_hash FROM import_batch_files f
    JOIN import_batches b ON b.id = f.batch_id
    WHERE b.status IN ('applied', 'legacy') AND f.file_hash = ANY($1::text[])
"""
RECENT_STAGED = """
    SELECT id, plan FROM import_batches
    WHERE status = 'staged' AND expires_at > now() ORDER BY created_at DESC LIMIT 20
"""
CSV_WITHOUT_OFX = """
    WITH last_csv AS (
      SELECT DISTINCT ON (f.account_id) f.account_id, f.file_hash, f.period_end
      FROM import_batch_files f JOIN import_batches b ON b.id = f.batch_id
      WHERE b.status = 'applied' AND f.source = 'nubank_csv' AND f.account_id IS NOT NULL
      ORDER BY f.account_id, f.period_end DESC, b.applied_at DESC
    )
    SELECT l.account_id, l.file_hash, l.period_end FROM last_csv l
    WHERE NOT EXISTS (
      SELECT 1 FROM import_batch_files o JOIN import_batches b ON b.id = o.batch_id
      WHERE b.status IN ('applied', 'legacy') AND o.source = 'nubank_ofx'
        AND o.account_id = l.account_id AND o.period_end >= l.period_end
    )
"""
COVERAGE = """
    SELECT f.source, f.account_id::text AS account_id, f.period_start, f.period_end
    FROM import_batch_files f JOIN import_batches b ON b.id = f.batch_id
    WHERE b.status IN ('applied', 'legacy') AND f.period_start IS NOT NULL
      AND f.period_end IS NOT NULL
"""
HISTORY = """
    SELECT id, status, plan, created_at, applied_at FROM import_batches
    WHERE status IN ('applied', 'undone', 'legacy')
    ORDER BY coalesce(applied_at, created_at) DESC, id LIMIT $1
"""
LAST_APPLIED = """
    SELECT id, applied_at, applied_at >= now() - interval '7 days' AS in_window
    FROM import_batches WHERE status = 'applied'
    ORDER BY applied_at DESC, id LIMIT 1
"""
LAST_ANY = """
    SELECT id, status, coalesce(applied_at, created_at) AS at FROM import_batches
    WHERE status IN ('applied', 'legacy') ORDER BY coalesce(applied_at, created_at) DESC LIMIT 1
"""
BATCH_SOURCES = "SELECT DISTINCT source FROM import_batch_files WHERE batch_id = $1::uuid"
MARK_UNDONE = """
    UPDATE import_batches SET status = 'undone', undone_at = now() WHERE id = $1::uuid
"""
DELETE_FILES = "DELETE FROM import_batch_files WHERE batch_id = $1::uuid"
