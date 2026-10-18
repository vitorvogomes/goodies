"""Story 2.8 — lançamento manual: source manual, sem lote, categoria por categorize (manual);
edição/remoção só de manual; importada só muda de categoria; mês marcado sujo."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.common.month_status import AllMonthsOpen, month_status, register_month_status


class _Spy(AllMonthsOpen):
    def __init__(self) -> None:
        self.dirty: list[date] = []

    async def mark_dirty(self, conn: Any, month: date) -> None:
        self.dirty.append(month)


async def _cat(pool: Any, key: str) -> str:
    async with pool.acquire() as conn:
        return str(await conn.fetchval("SELECT id FROM categories WHERE key = $1", key))


@pytest.mark.asyncio
async def test_create_edit_delete_manual(api, auth_headers, account, pool) -> None:
    spy, previous = _Spy(), month_status()
    register_month_status(spy)
    try:
        lazer = await _cat(pool, "gasto:lazer")
        resp = await api.post(
            "/api/v1/ledger/transactions",
            json={
                "account_id": account,
                "date": "2099-08-03",
                "amount": "-42.90",
                "description": "Cinema em dinheiro",
                "category_id": lazer,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        row = resp.json()
        assert row["source"] == "manual" and row["batch_id"] is None
        assert row["category_source"] == "manual" and row["review_status"] == "confirmed"
        assert row["amount"] == -42.9 and row["kind"] == "expense"

        upd = await api.patch(
            f"/api/v1/ledger/transactions/{row['id']}",
            json={"amount": "-45.00", "date": "2099-09-01"},
            headers=auth_headers,
        )
        assert upd.status_code == 200 and upd.json()["amount"] == -45.0
        assert upd.json()["date"] == "2099-09-01"
        assert {date(2099, 8, 1), date(2099, 9, 1)} <= set(spy.dirty)

        rm = await api.delete(f"/api/v1/ledger/transactions/{row['id']}", headers=auth_headers)
        assert rm.status_code == 204
        gone = await api.patch(
            f"/api/v1/ledger/transactions/{row['id']}", json={"amount": "-1"}, headers=auth_headers
        )
        assert gone.status_code == 404
    finally:
        register_month_status(previous)


@pytest.mark.asyncio
async def test_imported_only_changes_category(api, auth_headers, account, pool) -> None:
    async with pool.acquire() as conn:
        batch = await conn.fetchval(
            "INSERT INTO import_batches (status) VALUES ('applied') RETURNING id"
        )
        tx = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, description, "
            "batch_id, source) VALUES ($1, '2099-08-05', -10, 'Saída a classificar', 'imp', $2, "
            "'nubank_ofx') RETURNING id",
            account,
            batch,
        )
    try:
        edit = await api.patch(
            f"/api/v1/ledger/transactions/{tx}", json={"amount": "-99"}, headers=auth_headers
        )
        assert edit.status_code == 409
        assert edit.json()["detail"]["error"] == "transacao_importada"
        rm = await api.delete(f"/api/v1/ledger/transactions/{tx}", headers=auth_headers)
        assert rm.status_code == 409
        transporte = await _cat(pool, "gasto:transporte")
        ok = await api.patch(
            f"/api/v1/ledger/transactions/{tx}",
            json={"category_id": transporte},
            headers=auth_headers,
        )
        assert ok.status_code == 200 and ok.json()["category_name"] == "Transporte"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE id = $1", tx)
            await conn.execute("DELETE FROM import_batches WHERE id = $1", batch)


@pytest.mark.asyncio
async def test_validation(api, auth_headers, account, pool) -> None:
    lazer = await _cat(pool, "gasto:lazer")
    base = {"account_id": account, "date": "2099-08-03", "description": "x", "category_id": lazer}
    zero = await api.post(
        "/api/v1/ledger/transactions", json={**base, "amount": "0"}, headers=auth_headers
    )
    assert zero.status_code == 422
    floaty = await api.post(
        "/api/v1/ledger/transactions", json={**base, "amount": 1.5}, headers=auth_headers
    )
    assert floaty.status_code == 422  # dinheiro não aceita float (AD-4): o front manda string
    bad_cat = await api.post(
        "/api/v1/ledger/transactions",
        json={**base, "amount": "-1", "category_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert bad_cat.status_code == 422
