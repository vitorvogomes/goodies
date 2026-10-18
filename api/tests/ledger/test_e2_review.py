"""Achados do code review do Épico 2 — cada teste trava um defeito corrigido."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from engines.ledger import importer, service
from engines.ledger.importer import StatementEntry, import_statement

URL = "/api/v1/ledger"


async def _group(api, headers, key: str) -> dict:
    tree = (await api.get(f"{URL}/category-tree", headers=headers)).json()
    return next(g for g in tree if g["key"] == key)


@pytest.mark.asyncio
async def test_category_with_history_is_archived_not_deleted(api, auth_headers, account, pool):
    """Categoria sem transações hoje, mas com eventos de categorização → 409, não 500."""
    outros = await _group(api, auth_headers, "outros")
    cat = await api.post(
        f"{URL}/categories",
        json={"name": f"Hist {uuid.uuid4().hex[:6]}", "group_id": outros["id"]},
        headers=auth_headers,
    )
    cid = cat.json()["id"]
    lazer = await _group(api, auth_headers, "lazer")
    other = lazer["categories"][0]["id"]
    try:
        tx = await api.post(
            f"{URL}/transactions",
            json={
                "account_id": account,
                "date": "2099-06-01",
                "amount": "-10",
                "description": "x",
                "category_id": cid,
            },
            headers=auth_headers,
        )
        await api.patch(
            f"{URL}/transactions/{tx.json()['id']}/category",
            json={"category_id": other},
            headers=auth_headers,
        )
        rm = await api.delete(f"{URL}/categories/{cid}", headers=auth_headers)
        assert rm.status_code == 409
        assert rm.json()["detail"]["error"] == "categoria_com_historico"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1::uuid", account)
            await conn.execute("DELETE FROM categories WHERE id = $1::uuid", cid)


@pytest.mark.asyncio
async def test_move_keeps_chosen_role_and_refuses_role_of_other_kind(api, auth_headers, pool):
    outros = await _group(api, auth_headers, "outros")
    trabalho = await _group(api, auth_headers, "trabalho")
    cat = await api.post(
        f"{URL}/categories",
        json={"name": f"Mover {uuid.uuid4().hex[:6]}", "group_id": outros["id"]},
        headers=auth_headers,
    )
    cid = cat.json()["id"]
    try:
        mv = await api.patch(
            f"{URL}/categories/{cid}",
            json={"group_id": trabalho["id"], "role": "devolucao"},
            headers=auth_headers,
        )
        assert mv.status_code == 200
        assert (mv.json()["kind"], mv.json()["role"]) == ("income", "devolucao")
        bad = await api.patch(
            f"{URL}/categories/{cid}", json={"role": "consumo"}, headers=auth_headers
        )
        assert bad.status_code == 409 and bad.json()["detail"]["error"] == "papel_invalido"
        bad_new = await api.post(
            f"{URL}/categories",
            json={
                "name": f"Papel {uuid.uuid4().hex[:6]}",
                "group_id": outros["id"],
                "role": "resgate",
            },
            headers=auth_headers,
        )
        assert bad_new.status_code == 409
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM categories WHERE id = $1::uuid", cid)


@pytest.mark.asyncio
async def test_import_is_atomic(pool, account, monkeypatch):
    """Falha no categorize() desfaz o lote inteiro: nada fica preso 'a classificar'."""

    async def boom(*args, **kwargs):
        raise RuntimeError("falhou no meio")

    monkeypatch.setattr(importer.ledger_service, "categorize", boom)
    entries = [
        StatementEntry(uuid.uuid4().hex, datetime.date(2099, 3, 1), Decimal("-12"), "UBER *TRIP"),
    ]
    name = f"atomico-{uuid.uuid4().hex[:6]}.ofx"
    async with pool.acquire() as conn:
        with pytest.raises(RuntimeError):
            await import_statement(conn, uuid.UUID(account), entries, file_name=name)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE account_id = $1::uuid", account
            )
            == 0
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM import_batch_files WHERE file_name = $1", name
            )
            == 0
        )


@pytest.mark.asyncio
async def test_import_and_categorize_reach_portfolio_hook(pool, account, monkeypatch):
    """AD-5/AD-6: o portfolio registra o hook no main; import e categorize invalidam o XIRR."""
    import main  # noqa: F401 — registra os hooks
    from engines.portfolio import hooks

    calls: list[str] = []

    async def fake_invalidate(user_id: str) -> None:
        calls.append(user_id)

    monkeypatch.setattr(hooks, "invalidate_xirr_cache", fake_invalidate)
    assert hooks.on_transactions_changed in service._hooks
    entries = [
        StatementEntry(uuid.uuid4().hex, datetime.date(2099, 3, 2), Decimal("-15"), "Padaria"),
    ]
    async with pool.acquire() as conn:
        await import_statement(conn, uuid.UUID(account), entries)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_rules_of_archived_group_are_not_applied(api, auth_headers, pool):
    sfx = uuid.uuid4().hex[:6]
    grp = await api.post(
        f"{URL}/category-groups",
        json={"name": f"Arq {sfx}", "kind": "expense"},
        headers=auth_headers,
    )
    gid = grp.json()["id"]
    cat = await api.post(
        f"{URL}/categories", json={"name": f"ArqCat {sfx}", "group_id": gid}, headers=auth_headers
    )
    cid = cat.json()["id"]
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO category_rules (pattern, direction, category_id, origin) "
                "VALUES ($1, 'saida', $2::uuid, 'manual')",
                f"zzarq{sfx}",
                cid,
            )
            await api.patch(
                f"{URL}/category-groups/{gid}", json={"is_active": False}, headers=auth_headers
            )
            rules = await service.load_rules(conn)
        assert not any(r.pattern == f"zzarq{sfx}" for r in rules)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM category_rules WHERE category_id = $1::uuid", cid)
            await conn.execute("DELETE FROM categories WHERE id = $1::uuid", cid)
            await conn.execute("DELETE FROM category_groups WHERE id = $1::uuid", gid)


@pytest.mark.asyncio
async def test_unknown_or_malformed_ids_are_4xx(api, auth_headers, account):
    lazer = await _group(api, auth_headers, "lazer")
    body = {
        "account_id": str(uuid.uuid4()),
        "date": "2099-06-01",
        "amount": "-10",
        "category_id": lazer["categories"][0]["id"],
    }
    r = await api.post(f"{URL}/transactions", json=body, headers=auth_headers)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "conta_inexistente"
    r = await api.post(
        f"{URL}/transactions", json={**body, "account_id": "abc"}, headers=auth_headers
    )
    assert r.status_code == 422
    r = await api.patch(
        f"{URL}/transactions/abc/category", json={"category_id": "x"}, headers=auth_headers
    )
    assert r.status_code == 422
    r = await api.patch(
        f"{URL}/transactions/{uuid.uuid4()}/category",
        json={"category_id": lazer["categories"][0]["id"]},
        headers=auth_headers,
    )
    assert r.status_code == 404
    r = await api.patch(f"{URL}/rules/abc", json={"is_active": False}, headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reapply_invalid_month_message(api, auth_headers):
    r = await api.post(
        f"{URL}/rules/reapply/preview",
        json={"de": "2026-13", "ate": "2026-12"},
        headers=auth_headers,
    )
    assert r.status_code == 422
    assert r.json()["detail"]["message"] == "Período inválido (use AAAA-MM)."
