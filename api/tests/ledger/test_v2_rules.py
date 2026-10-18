"""Story 2.10 — Ajustes › Regras: listar, editar/desativar, prévia das afetadas (não grava) e
reaplicar ao período (prévia antes × depois; confirmar via categorize; manual intocada)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

URL = "/api/v1/ledger"


async def _setup(pool: Any, account: str, sfx: str) -> dict[str, str]:
    async with pool.acquire() as conn:
        lazer = str(await conn.fetchval("SELECT id FROM categories WHERE key = 'gasto:lazer'"))
        transp = str(
            await conn.fetchval("SELECT id FROM categories WHERE key = 'gasto:transporte'")
        )
        rule = str(
            await conn.fetchval(
                "INSERT INTO category_rules (pattern, direction, category_id, origin) "
                "VALUES ($1, 'saida', $2, 'review') RETURNING id",
                f"zzr{sfx}",
                transp,
            )
        )
        ids = {}
        for name, src, cat in (("auto", "suggestion", lazer), ("manual", "manual", lazer)):
            ids[name] = str(
                await conn.fetchval(
                    "INSERT INTO transactions (account_id, date, amount, category, category_id, "
                    "kind, description, category_source) VALUES ($1, '2096-02-10', -20, 'Lazer', "
                    "$2, 'expense', $3, $4) RETURNING id",
                    account,
                    cat,
                    f"ZZR{sfx} {name}",
                    src,
                )
            )
    return {**ids, "rule": rule, "lazer": lazer, "transp": transp}


@pytest.mark.asyncio
async def test_list_edit_preview_and_reapply(api, auth_headers, account, pool) -> None:
    sfx = "x" + uuid.uuid4().hex[:6]  # "x": "ZZR" + hex nunca forma "rdb" (regra legado)
    ids = await _setup(pool, account, sfx)
    try:
        rules = (await api.get(f"{URL}/rules", headers=auth_headers)).json()
        mine = next(r for r in rules if r["id"] == ids["rule"])
        assert (
            mine["pattern"] == f"zzr{sfx}" and mine["category_label"] == "Transporte › Transporte"
        )
        assert mine["is_active"] is True and mine["direction"] == "saida"

        prev = await api.post(
            f"{URL}/rules/preview",
            json={"pattern": f"ZZR{sfx}", "direction": "saida"},
            headers=auth_headers,
        )
        assert prev.status_code == 200 and prev.json()["total"] == 2  # não grava

        rp = await api.post(
            f"{URL}/rules/reapply/preview",
            json={"de": "2096-02", "ate": "2096-02"},
            headers=auth_headers,
        )
        body = rp.json()
        assert [c["transaction_id"] for c in body["changes"]] == [ids["auto"]]
        change = body["changes"][0]
        assert (change["before"], change["after"]) == ("Lazer › Lazer", "Transporte › Transporte")
        assert body["manual_unchanged"] == 1 and body["closed_months"] == 0

        ok = await api.post(
            f"{URL}/rules/reapply", json={"de": "2096-02", "ate": "2096-02"}, headers=auth_headers
        )
        assert ok.status_code == 200 and ok.json()["changed"] == 1
        async with pool.acquire() as conn:
            rows = dict(
                await conn.fetch(
                    "SELECT id::text, category_source || ':' || category FROM transactions "
                    "WHERE id = ANY($1::uuid[])",
                    [ids["auto"], ids["manual"]],
                )
            )
            cause = await conn.fetchval(
                "SELECT cause FROM categorization_events WHERE transaction_id = $1", ids["auto"]
            )
        assert rows[ids["auto"]] == "rule:Transporte" and rows[ids["manual"]] == "manual:Lazer"
        assert cause == "reapply"

        # desativar: não aplica mais, mas quem já categorizou mantém
        off = await api.patch(
            f"{URL}/rules/{ids['rule']}", json={"is_active": False}, headers=auth_headers
        )
        assert off.status_code == 200 and off.json()["is_active"] is False
        again = await api.post(
            f"{URL}/rules/reapply/preview",
            json={"de": "2096-02", "ate": "2096-02"},
            headers=auth_headers,
        )
        assert again.json()["changes"] == []
        async with pool.acquire() as conn:
            kept = await conn.fetchval(
                "SELECT category FROM transactions WHERE id = $1", ids["auto"]
            )
        assert kept == "Transporte"

        edit = await api.patch(
            f"{URL}/rules/{ids['rule']}",
            json={"pattern": f"zzr{sfx} x", "category_id": ids["lazer"], "direction": "ambos"},
            headers=auth_headers,
        )
        assert edit.status_code == 200 and edit.json()["direction"] == "ambos"
        bad = await api.patch(
            f"{URL}/rules/{ids['rule']}", json={"pattern": "  "}, headers=auth_headers
        )
        assert bad.status_code == 422
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", account)
            await conn.execute("DELETE FROM category_rules WHERE id = $1", ids["rule"])


@pytest.mark.asyncio
async def test_reapply_period_validation(api, auth_headers) -> None:
    bad = await api.post(
        f"{URL}/rules/reapply/preview",
        json={"de": "2096-05", "ate": "2096-02"},
        headers=auth_headers,
    )
    assert bad.status_code == 422
