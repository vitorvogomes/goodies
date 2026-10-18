"""Story 2.7 — GET /api/v1/ledger/transactions (paginada, Money, origem e lote), correção de
categoria pela linha (categorize, manual) e as opções do Combobox de categoria."""

from __future__ import annotations

from typing import Any

import pytest

from engines.ingest import service as ingest_service
from engines.ingest.models import BatchFileIn


async def _seed(pool: Any, account: str) -> dict[str, str]:
    async with pool.acquire() as conn:
        rule_cat = await conn.fetchval("SELECT id FROM categories WHERE key = 'gasto:lazer'")
        rule = await conn.fetchval(
            "INSERT INTO category_rules (pattern, direction, category_id) "
            "VALUES ('zz-cine-27', 'saida', $1) RETURNING id",
            rule_cat,
        )
        batch = await ingest_service.record_applied_batch(
            conn, [BatchFileIn(source="nubank_ofx", account_id=account, file_name="jul.ofx")]
        )
        tx_rule = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description, batch_id, source, category_source, category_rule_id, review_status, "
            "payer) VALUES ($1, '2099-07-10', -45.50, 'Lazer', $2, 'expense', 'ZZ-CINE-27 sala 3', "
            "$3, 'nubank_ofx', 'rule', $4, 'confirmed', NULL) RETURNING id",
            account,
            rule_cat,
            batch,
            rule,
        )
        rec = await conn.fetchval("SELECT id FROM categories WHERE key = 'trabalho:recorrente'")
        tx_income = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description, category_source, review_status, payer) "
            "VALUES ($1, '2099-07-05', 7000, 'Recorrente', $2, 'income', 'PIX salário', "
            "'manual', 'confirmed', 'Flash Capital') RETURNING id",
            account,
            rec,
        )
    return {"rule": str(tx_rule), "income": str(tx_income), "rule_id": str(rule), "batch": batch}


@pytest.mark.asyncio
async def test_list_month_paginated_with_provenance(api, auth_headers, account, pool) -> None:
    ids = await _seed(pool, account)
    try:
        resp = await api.get(
            "/api/v1/ledger/transactions?periodo=2099-07&limit=50", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"items", "total", "limit", "offset"}
        mine = {i["id"]: i for i in body["items"] if i["id"] in ids.values()}
        assert len(mine) == 2
        row = mine[ids["rule"]]
        assert row["amount"] == -45.5 and row["kind_label"] == "Despesa"
        assert (row["group_name"], row["category_name"]) == ("Lazer", "Lazer")
        assert row["category_source"] == "rule" and row["rule_pattern"] == "zz-cine-27"
        assert row["source"] == "nubank_ofx" and row["batch_id"] == ids["batch"]
        assert row["file_name"] == "jul.ofx"
        income = mine[ids["income"]]
        assert income["payer"] == "Flash Capital" and income["kind_label"] == "Receita"
        assert income["group_name"] == "Trabalho"
        # mais recente primeiro
        dates = [i["date"] for i in body["items"]]
        assert dates == sorted(dates, reverse=True)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", account)
            await conn.execute("DELETE FROM category_rules WHERE pattern = 'zz-cine-27'")


@pytest.mark.asyncio
async def test_inline_correction_goes_through_categorize(api, auth_headers, account, pool) -> None:
    ids = await _seed(pool, account)
    try:
        async with pool.acquire() as conn:
            transporte = str(
                await conn.fetchval("SELECT id FROM categories WHERE key = 'gasto:transporte'")
            )
        resp = await api.patch(
            f"/api/v1/ledger/transactions/{ids['rule']}/category",
            json={"category_id": transporte},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        row = resp.json()
        assert row["category_name"] == "Transporte" and row["category_source"] == "manual"
        async with pool.acquire() as conn:
            cause = await conn.fetchval(
                "SELECT cause FROM categorization_events WHERE transaction_id = $1", ids["rule"]
            )
        assert cause == "inline_edit"
        missing = await api.patch(
            f"/api/v1/ledger/transactions/{ids['rule']}/category",
            json={"category_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth_headers,
        )
        assert missing.status_code == 422
        assert missing.json()["detail"]["error"] == "categoria_inexistente"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", account)
            await conn.execute("DELETE FROM category_rules WHERE pattern = 'zz-cine-27'")


@pytest.mark.asyncio
async def test_category_options_hide_archived_and_label_group(api, auth_headers) -> None:
    resp = await api.get("/api/v1/ledger/categories", headers=auth_headers)
    assert resp.status_code == 200
    opts = resp.json()
    labels = {o["label"] for o in opts}
    assert "Alimentação › Alimentação" in labels and "Lazer › Viagem" in labels
    assert not any(o["key"].startswith("legado:") for o in opts)  # arquivadas não aparecem
    assert not any(o["key"].startswith("sistema:") for o in opts)  # a classificar não é opção
    archived = await api.get(
        "/api/v1/ledger/categories?incluir_arquivadas=true", headers=auth_headers
    )
    assert any(o["key"] == "legado:betuel" for o in archived.json())


@pytest.mark.asyncio
async def test_empty_period_and_auth(api, auth_headers) -> None:
    resp = await api.get("/api/v1/ledger/transactions?periodo=2098-01", headers=auth_headers)
    assert resp.json()["items"] == [] and resp.json()["total"] == 0
    assert (await api.get("/api/v1/ledger/transactions?periodo=2098-01")).status_code == 401
    bad = await api.get("/api/v1/ledger/transactions?periodo=2098-13", headers=auth_headers)
    assert bad.status_code == 422
