"""Story 3.10 — Revisão de transações: lista das `pending` do lote (tag de origem, agrupada por mês
com subtotais), confirmação em lote via categorize() (troca vira manual) e o aviso de pendentes."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from engines.ledger.importer import StatementEntry, import_statement

URL = "/api/v1/ledger/review"


@pytest.mark.asyncio
async def test_review_list_confirm_and_alert(api, auth_headers, account, pool) -> None:
    import main  # noqa: F401
    from engines.alerts import service as alerts_service

    entries = [
        StatementEntry(
            uuid.uuid4().hex, datetime.date(2099, 5, 2), Decimal("-20"), "Aplicação RDB caixinha"
        ),
        StatementEntry(
            uuid.uuid4().hex, datetime.date(2099, 6, 3), Decimal("-9"), f"Coisa {uuid.uuid4().hex}"
        ),
        StatementEntry(
            uuid.uuid4().hex,
            datetime.date(2099, 6, 4),
            Decimal("15"),
            f"Entrada {uuid.uuid4().hex}",
        ),
    ]
    async with pool.acquire() as conn:
        await import_statement(conn, uuid.UUID(account), entries)
        batch = str(
            await conn.fetchval(
                "SELECT batch_id FROM transactions WHERE account_id = $1::uuid LIMIT 1", account
            )
        )
    r = await api.get(f"{URL}?lote={batch}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    by_desc = {i["description"]: i for i in body["items"]}
    assert by_desc["Aplicação RDB caixinha"]["origin"] == "regra"
    assert by_desc[entries[1].description]["origin"] == "sem_sugestao"
    assert [(m["month"], m["count"]) for m in body["months"]] == [("2099-05", 1), ("2099-06", 2)]
    june = body["months"][1]
    assert (june["entradas"], june["saidas"]) == (15.0, -9.0)

    async with pool.acquire() as conn:
        alerts = await alerts_service.active_alerts(conn)
    pend = [a for a in alerts.items if a.key == "transacoes_a_revisar"]
    assert pend and pend[0].message.endswith("transações a revisar.")
    assert pend[0].action.label == "Revisar"

    # "a classificar" não confirma
    sem = by_desc[entries[1].description]
    bad = await api.post(
        f"{URL}/confirm",
        json={"items": [{"transaction_id": sem["id"], "category_id": sem["category_id"]}]},
        headers=auth_headers,
    )
    assert bad.status_code == 422 and bad.json()["detail"]["error"] == "sem_categoria"

    uber = by_desc["Aplicação RDB caixinha"]
    other = await _other_expense(pool, uber["category_id"])
    ok = await api.post(
        f"{URL}/confirm",
        json={
            "lote": batch,
            "items": [
                {"transaction_id": uber["id"], "category_id": uber["category_id"]},
                {"transaction_id": sem["id"], "category_id": other},
            ],
        },
        headers=auth_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"confirmed": 2, "remaining": 1}
    async with pool.acquire() as conn:
        rows = {
            str(r["id"]): r
            for r in await conn.fetch(
                "SELECT id, review_status, category_source FROM transactions "
                "WHERE account_id = $1::uuid",
                account,
            )
        }
    assert (rows[uber["id"]]["review_status"], rows[uber["id"]]["category_source"]) == (
        "confirmed",
        "rule",
    )
    assert (rows[sem["id"]]["review_status"], rows[sem["id"]]["category_source"]) == (
        "confirmed",
        "manual",
    )
    left = (await api.get(f"{URL}?lote={batch}", headers=auth_headers)).json()
    assert left["total"] == 1


async def _other_expense(pool, not_this: str) -> str:
    async with pool.acquire() as conn:
        return str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system AND c.is_active AND c.id <> $1::uuid "
                "ORDER BY c.key LIMIT 1",
                not_this,
            )
        )
