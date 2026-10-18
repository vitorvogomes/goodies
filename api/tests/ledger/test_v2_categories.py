"""Story 2.9 — Ajustes › Categorias: árvore, criar, renomear (regrava o texto legado), mover
(regrava o kind via categorize), arquivar, apagar só sem transações, tipo de grupo travado."""

from __future__ import annotations

import uuid

import pytest

URL = "/api/v1/ledger"


@pytest.mark.asyncio
async def test_tree_and_crud(api, auth_headers, account, pool) -> None:
    sfx = uuid.uuid4().hex[:6]
    created: list[str] = []
    try:
        tree = (await api.get(f"{URL}/category-tree", headers=auth_headers)).json()
        lazer = next(g for g in tree if g["key"] == "lazer")
        assert lazer["kind"] == "expense" and lazer["kind_label"] == "Gasto"
        assert {c["name"] for c in lazer["categories"]} >= {"Viagem", "Lazer"}
        assert not any(g["is_system"] for g in tree)  # grupos de sistema não aparecem

        grp = await api.post(
            f"{URL}/category-groups",
            json={"name": f"Pets {sfx}", "kind": "expense"},
            headers=auth_headers,
        )
        assert grp.status_code == 201
        gid = grp.json()["id"]
        cat = await api.post(
            f"{URL}/categories",
            json={"name": f"Ração {sfx}", "group_id": gid},
            headers=auth_headers,
        )
        assert cat.status_code == 201
        c = cat.json()
        created.append(c["id"])
        assert (c["kind"], c["role"]) == ("expense", "consumo")  # herda tipo e role padrão
        dup = await api.post(
            f"{URL}/categories",
            json={"name": f"Ração {sfx}", "group_id": gid},
            headers=auth_headers,
        )
        assert dup.status_code == 409

        # transação nela → só arquivar; renome regrava o texto legado
        tx = await api.post(
            f"{URL}/transactions",
            json={
                "account_id": account,
                "date": "2099-06-01",
                "amount": "-10",
                "description": "x",
                "category_id": c["id"],
            },
            headers=auth_headers,
        )
        assert tx.status_code == 201
        rm = await api.delete(f"{URL}/categories/{c['id']}", headers=auth_headers)
        assert rm.status_code == 409 and rm.json()["detail"]["error"] == "categoria_com_transacoes"
        ren = await api.patch(
            f"{URL}/categories/{c['id']}", json={"name": f"Petshop {sfx}"}, headers=auth_headers
        )
        assert ren.status_code == 200
        async with pool.acquire() as conn:
            text = await conn.fetchval(
                "SELECT category FROM transactions WHERE id = $1", tx.json()["id"]
            )
        assert text == f"Petshop {sfx}"

        # tipo de grupo com transações não muda
        kind = await api.patch(
            f"{URL}/category-groups/{gid}", json={"kind": "income"}, headers=auth_headers
        )
        assert kind.status_code == 409 and kind.json()["detail"]["error"] == "tipo_com_transacoes"

        # mover para grupo de outro tipo regrava o kind das transações (categorize, cause move)
        trabalho = next(g for g in tree if g["key"] == "trabalho")
        mv = await api.patch(
            f"{URL}/categories/{c['id']}", json={"group_id": trabalho["id"]}, headers=auth_headers
        )
        assert mv.status_code == 200 and mv.json()["kind"] == "income"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT t.kind, (SELECT cause FROM categorization_events e "
                "WHERE e.transaction_id = t.id ORDER BY created_at DESC LIMIT 1) cause "
                "FROM transactions t WHERE t.id = $1",
                tx.json()["id"],
            )
        assert (row["kind"], row["cause"]) == ("income", "move")

        arch = await api.patch(
            f"{URL}/categories/{c['id']}", json={"is_active": False}, headers=auth_headers
        )
        assert arch.status_code == 200 and arch.json()["is_active"] is False
        hidden = (await api.get(f"{URL}/category-tree", headers=auth_headers)).json()
        assert not any(x["id"] == c["id"] for g in hidden for x in g["categories"])
        shown = (
            await api.get(f"{URL}/category-tree?incluir_arquivadas=true", headers=auth_headers)
        ).json()
        assert any(x["id"] == c["id"] for g in shown for x in g["categories"])
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", account)
            for cid in created:
                await conn.execute("DELETE FROM categories WHERE id = $1", cid)
            await conn.execute("DELETE FROM category_groups WHERE name LIKE 'Pets %'")


@pytest.mark.asyncio
async def test_empty_category_can_be_deleted_and_system_is_locked(api, auth_headers, pool) -> None:
    sfx = uuid.uuid4().hex[:6]
    tree = (await api.get(f"{URL}/category-tree", headers=auth_headers)).json()
    outros = next(g for g in tree if g["key"] == "outros")
    cat = await api.post(
        f"{URL}/categories",
        json={"name": f"Vazia {sfx}", "group_id": outros["id"]},
        headers=auth_headers,
    )
    rm = await api.delete(f"{URL}/categories/{cat.json()['id']}", headers=auth_headers)
    assert rm.status_code == 204
    async with pool.acquire() as conn:
        sys_id = await conn.fetchval(
            "SELECT id FROM categories WHERE key = 'sistema:saida_a_classificar'"
        )
    locked = await api.patch(
        f"{URL}/categories/{sys_id}", json={"name": "Outra coisa"}, headers=auth_headers
    )
    assert locked.status_code == 409 and locked.json()["detail"]["error"] == "categoria_de_sistema"


@pytest.mark.asyncio
async def test_v1_screens_group_the_same_after_rename(api, auth_headers, account, pool) -> None:
    """Fumaça v1: o by-category do dashboard agrupa igual antes e depois do renome."""
    sfx = uuid.uuid4().hex[:6]
    tree = (await api.get(f"{URL}/category-tree", headers=auth_headers)).json()
    outros = next(g for g in tree if g["key"] == "outros")
    cat = (
        await api.post(
            f"{URL}/categories",
            json={"name": f"Smoke {sfx}", "group_id": outros["id"]},
            headers=auth_headers,
        )
    ).json()
    try:
        for amount in ("-10", "-15"):
            await api.post(
                f"{URL}/transactions",
                json={
                    "account_id": account,
                    "date": "2097-03-02",
                    "amount": amount,
                    "description": "smoke",
                    "category_id": cat["id"],
                },
                headers=auth_headers,
            )

        async def groups() -> dict[str, float]:
            body = (
                await api.get("/api/v1/cashflow/by-category?month=2097-03", headers=auth_headers)
            ).json()
            return {r["category"]: r["total"] for r in body["expense"]}

        before = await groups()
        await api.patch(
            f"{URL}/categories/{cat['id']}",
            json={"name": f"Smoke novo {sfx}"},
            headers=auth_headers,
        )
        after = await groups()
        assert before[f"Smoke {sfx}"] == after[f"Smoke novo {sfx}"] == 25.0
        assert len(before) == len(after)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", account)
            await conn.execute("DELETE FROM categories WHERE id = $1", cat["id"])
