"""Story 6.1 — custos fixos v2: vigência (`valid_from`/`valid_to`), CRUD de Ajustes com Money e
categoria, "Vencimento entre 1 e 31.", casamento do mês pelo serviço, e o desfazer do lote levando a
decisão de `fixed_cost_payments` junto (FK ON DELETE CASCADE)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest

from tests.ingest.conftest import ofx_account as ofx_account

URL = "/api/v1/ledger/fixed-costs"


async def _category(pool: Any) -> str:
    async with pool.acquire() as conn:
        return str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
            )
        )


@pytest.mark.asyncio
async def test_crud_and_validation(api, auth_headers, pool) -> None:
    cat = await _category(pool)
    name = f"Plano {uuid.uuid4().hex[:6]}"
    r = await api.post(
        URL,
        json={"name": name, "amount": "450.00", "due_day": 10, "category_id": cat},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["amount"] == 450.0 and created["valid_from"].endswith("-01")
    assert created["valid_to"] is None and created["category_label"]
    bad = await api.post(
        URL,
        json={"name": "x", "amount": "1.00", "due_day": 32, "category_id": cat},
        headers=auth_headers,
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["message"] == "Vencimento entre 1 e 31."
    r = await api.patch(f"{URL}/{created['id']}", json={"amount": "470.00"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["amount"] == 470.0
    listed = (await api.get(URL, headers=auth_headers)).json()
    assert any(c["id"] == created["id"] for c in listed)
    r = await api.delete(f"{URL}/{created['id']}", headers=auth_headers)
    assert r.status_code == 204
    async with pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM fixed_costs WHERE id = $1::uuid", created["id"]
        )


@pytest.mark.asyncio
async def test_vigencia_and_month_match(pool, account) -> None:
    from engines.ledger import service as ledger

    cat = await _category(pool)
    async with pool.acquire() as conn:
        ids = []
        for name, frm, to in (
            ("Antigo", "2098-01-01", "2098-02-01"),
            ("Atual", "2098-03-01", None),
        ):
            ids.append(
                await conn.fetchval(
                    "INSERT INTO fixed_costs (name, amount, due_day, category_id, valid_from, "
                    "valid_to) VALUES ($1, 100, 10, $2, $3, $4) RETURNING id",
                    f"{name} {uuid.uuid4().hex[:6]}",
                    uuid.UUID(cat),
                    date.fromisoformat(frm),
                    date.fromisoformat(to) if to else None,
                )
            )
        tx = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
            "description) VALUES ($1::uuid, '2098-03-11', -100.00, $2, 'expense', 'plano') "
            "RETURNING id",
            account,
            uuid.UUID(cat),
        )
        try:
            feb = {m.cost_id for m in await ledger.fixed_cost_matches(conn, date(2098, 2, 1))}
            mar = {m.cost_id: m for m in await ledger.fixed_cost_matches(conn, date(2098, 3, 1))}
            assert str(ids[0]) in feb and str(ids[1]) not in feb
            assert str(ids[0]) not in mar
            assert mar[str(ids[1])].transaction_id == str(tx)
        finally:
            await conn.execute("DELETE FROM fixed_costs WHERE id = ANY($1::uuid[])", ids)


@pytest.mark.asyncio
async def test_undo_batch_removes_decision(api, auth_headers, ofx_account, pool) -> None:
    """Regressão do desfazer (Story 3.14): a transação casada some com o lote e a decisão vai
    junto."""
    import main  # noqa: F401
    from tests.ingest.test_protocol import _ofx, _preview

    _, number = ofx_account
    body = (
        await _preview(
            api, auth_headers, [("fc.ofx", _ofx(number, [uuid.uuid4().hex], "20980410"))]
        )
    ).json()
    r = await api.post(
        "/api/v1/ingest/confirm",
        json={"batch_id": body["batch_id"], "hash": body["hash"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    cat = await _category(pool)
    async with pool.acquire() as conn:
        tx = await conn.fetchval(
            "SELECT id FROM transactions WHERE batch_id = $1::uuid", body["batch_id"]
        )
        cost = await conn.fetchval(
            "INSERT INTO fixed_costs (name, amount, due_day, category_id) VALUES ($1, 10, 10, "
            "$2) RETURNING id",
            f"Undo {uuid.uuid4().hex[:6]}",
            uuid.UUID(cat),
        )
        await conn.execute(
            "INSERT INTO fixed_cost_payments (fixed_cost_id, month, kind, transaction_id) "
            "VALUES ($1, '2098-04-01', 'confirmado', $2)",
            cost,
            tx,
        )
    try:
        r = await api.post(f"/api/v1/ingest/batches/{body['batch_id']}/undo", headers=auth_headers)
        assert r.status_code == 200, r.text
        async with pool.acquire() as conn:
            assert not await conn.fetchval(
                "SELECT count(*) FROM fixed_cost_payments WHERE fixed_cost_id = $1", cost
            )
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM fixed_costs WHERE id = $1", cost)
