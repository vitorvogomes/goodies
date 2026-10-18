"""Story 3.5 — operação de caixinha ligada à transação: derivada pelo hook, idempotente por
`transaction_id`, removida quando a transação deixa de ser caixinha; `protected` nunca muda."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

import pytest

from engines.common.owner import get_owner_id
from engines.ledger import service as ledger_service
from engines.ledger.importer import StatementEntry, import_statement
from engines.portfolio.caixinhas import derive_caixinha_ops


async def _ops(conn: Any, ids: list[str]) -> dict[str, Any]:
    rows = await conn.fetch(
        "SELECT transaction_id::text AS tx, asset_symbol, tipo, quantidade, protected "
        "FROM asset_operations WHERE transaction_id = ANY($1::uuid[])",
        ids,
    )
    return {r["tx"]: r for r in rows}


@pytest.mark.asyncio
async def test_derivation_follows_the_transaction(pool: Any) -> None:
    import main  # noqa: F401 — registra on_transactions_changed do portfolio

    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
            f"cx-{uuid.uuid4().hex[:6]}",
        )
        try:
            entries = [
                StatementEntry(
                    uuid.uuid4().hex,
                    datetime.date(2099, 5, 2),
                    Decimal("-100"),
                    "Aplicação RDB caixinha Turbo",
                ),
                StatementEntry(
                    uuid.uuid4().hex,
                    datetime.date(2099, 5, 9),
                    Decimal("40"),
                    "Resgate RDB caixinha Turbo",
                ),
            ]
            await import_statement(conn, acc, entries)
            ids = [
                str(r["id"])
                for r in await conn.fetch(
                    "SELECT id FROM transactions WHERE account_id = $1 ORDER BY date", acc
                )
            ]
            ops = await _ops(conn, ids)
            assert [(ops[i]["asset_symbol"], ops[i]["tipo"]) for i in ids] == [
                ("Nubank-Turbo", "aporte"),
                ("Nubank-Turbo", "resgate"),
            ]
            owner = await get_owner_id(conn)
            again = await derive_caixinha_ops(conn, owner, ids)
            assert again == {"created": 0, "updated": 0, "deleted": 0}

            # curadoria: protegida não muda nem some
            await conn.execute(
                "UPDATE asset_operations SET protected = true, quantidade = 33 "
                "WHERE transaction_id = $1::uuid",
                ids[1],
            )
            await derive_caixinha_ops(conn, owner, ids)
            assert (await _ops(conn, ids))[ids[1]]["quantidade"] == Decimal("33")

            # a transação deixa de ser caixinha: a operação derivada sai
            lazer = await conn.fetchval(
                "SELECT id FROM categories WHERE role = 'consumo' AND is_active "
                "ORDER BY key LIMIT 1"
            )
            await ledger_service.categorize(
                conn,
                [ledger_service.CategoryChange(ids[0], str(lazer), "manual")],
                cause="review",
            )
            assert ids[0] not in await _ops(conn, ids)
        finally:
            await conn.execute(
                "DELETE FROM asset_operations o USING transactions t "
                "WHERE o.transaction_id = t.id AND t.account_id = $1",
                acc,
            )
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
