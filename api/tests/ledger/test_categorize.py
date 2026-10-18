"""Story 2.5 — `ledger.service.categorize()`, o caminho único de mudança de categoria."""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from engines.common.month_status import AllMonthsOpen, month_status, register_month_status
from engines.ledger import service
from engines.ledger.service import CategoryChange


async def _cat(conn: Any, key: str) -> str:
    return str(await conn.fetchval("SELECT id FROM categories WHERE key = $1", key))


async def _tx(conn: Any, amount: float = -50, when: date = date(2099, 7, 3)) -> str:
    acc = await conn.fetchval(
        "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
        f"cat-{uuid.uuid4().hex[:6]}",
    )
    return str(
        await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category) "
            "VALUES ($1, $2, $3, 'Saída a classificar') RETURNING id",
            acc,
            when,
            amount,
        )
    )


class _Spy(AllMonthsOpen):
    def __init__(self) -> None:
        self.dirty: list[date] = []

    async def mark_dirty(self, conn: Any, month: date) -> None:
        self.dirty.append(month)


@pytest.mark.asyncio
async def test_writes_category_kind_text_source_and_event(pool: Any) -> None:
    calls: list[list[str]] = []

    async def hook(conn: Any, ids: list[str]) -> None:
        calls.append(ids)

    spy, previous = _Spy(), month_status()
    register_month_status(spy)
    service.register_on_transactions_changed(hook)
    try:
        async with pool.acquire() as conn, conn.transaction():
            tx = await _tx(conn)
            toro = await _cat(conn, "invest:toro_b3")
            res = await service.categorize(
                conn, [CategoryChange(tx, toro, "manual")], cause="inline_edit"
            )
            row = await conn.fetchrow(
                "SELECT category, kind, category_source, category_id FROM transactions "
                "WHERE id = $1",
                tx,
            )
            ev = await conn.fetchrow(
                "SELECT source, cause, after_category_id FROM categorization_events "
                "WHERE transaction_id = $1",
                tx,
            )
            raise _Rollback  # nada fica no banco de teste
    except _Rollback:
        pass
    finally:
        service.unregister_on_transactions_changed(hook)
        register_month_status(previous)
    assert res.changed == [tx]
    assert (row["category"], row["kind"], row["category_source"]) == (
        "Toro (B3)",
        "investment",
        "manual",
    )
    assert (ev["source"], ev["cause"], str(ev["after_category_id"])) == (
        "manual",
        "inline_edit",
        toro,
    )
    assert calls == [[tx]]
    assert spy.dirty == [date(2099, 7, 1)]


@pytest.mark.asyncio
async def test_manual_is_never_overwritten_by_rule_or_suggestion(pool: Any) -> None:
    try:
        async with pool.acquire() as conn, conn.transaction():
            tx = await _tx(conn)
            lazer = await _cat(conn, "gasto:lazer")
            transporte = await _cat(conn, "gasto:transporte")
            await service.categorize(conn, [CategoryChange(tx, lazer, "manual")], cause="review")
            res = await service.categorize(
                conn, [CategoryChange(tx, transporte, "rule", "r1")], cause="reapply"
            )
            res2 = await service.categorize(
                conn, [CategoryChange(tx, transporte, "suggestion")], cause="import"
            )
            final = await conn.fetchval("SELECT category FROM transactions WHERE id = $1", tx)
            raise _Rollback
    except _Rollback:
        pass
    assert res.kept_manual == [tx] and res2.kept_manual == [tx]
    assert final == "Lazer"


@pytest.mark.asyncio
async def test_no_change_no_event_and_hooks_can_be_suppressed(pool: Any) -> None:
    calls: list[list[str]] = []

    async def hook(conn: Any, ids: list[str]) -> None:
        calls.append(ids)

    service.register_on_transactions_changed(hook)
    try:
        async with pool.acquire() as conn, conn.transaction():
            tx = await _tx(conn)
            lazer = await _cat(conn, "gasto:lazer")
            await service.categorize(
                conn, [CategoryChange(tx, lazer, "suggestion")], cause="import", fire_hooks=False
            )
            again = await service.categorize(
                conn, [CategoryChange(tx, lazer, "suggestion")], cause="import", fire_hooks=False
            )
            events = await conn.fetchval(
                "SELECT count(*) FROM categorization_events WHERE transaction_id = $1", tx
            )
            raise _Rollback
    except _Rollback:
        pass
    finally:
        service.unregister_on_transactions_changed(hook)
    assert again.changed == [] and events == 1 and calls == []


class _Rollback(Exception):
    pass


def test_no_category_update_outside_categorize() -> None:
    """Nenhum UPDATE de categoria/kind de transação fora de `ledger.service.categorize()`."""
    api = Path(__file__).resolve().parents[2]
    allowed = {"engines/ledger/queries.py"}  # APPLY_CATEGORY, usado só por categorize()
    pattern = re.compile(
        r"UPDATE\s+transactions\b[^;\"]*?\bSET\b[^;]*?\b(category|category_id|kind)\s*=",
        re.IGNORECASE | re.DOTALL,
    )
    offenders = []
    for folder in ("engines", "workers", "hermes", "scripts/ops"):
        for f in sorted((api / folder).rglob("*.py")):
            rel = f.relative_to(api).as_posix()
            if rel in allowed or "__pycache__" in f.parts:
                continue
            if pattern.search(f.read_text()):
                offenders.append(rel)
    assert offenders == []
