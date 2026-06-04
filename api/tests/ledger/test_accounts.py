"""CRUD de contas (STORY-01-02)."""

import uuid
from datetime import date


async def test_accounts_requires_auth(api):
    resp = await api.get("/api/v1/accounts")
    assert resp.status_code == 401


async def test_create_and_list_account(api, auth_headers):
    name = f"Nubank-{uuid.uuid4().hex[:8]}"
    created = await api.post(
        "/api/v1/accounts",
        json={"name": name, "type": "bank"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == name
    assert body["type"] == "bank"
    assert body["currency"] == "BRL"

    listed = await api.get("/api/v1/accounts", headers=auth_headers)
    assert listed.status_code == 200
    assert any(a["id"] == body["id"] for a in listed.json())

    await api.delete(f"/api/v1/accounts/{body['id']}", headers=auth_headers)


async def test_update_account(api, auth_headers):
    created = await api.post(
        "/api/v1/accounts",
        json={"name": f"acc-{uuid.uuid4().hex[:8]}", "type": "manual"},
        headers=auth_headers,
    )
    acc_id = created.json()["id"]
    updated = await api.put(
        f"/api/v1/accounts/{acc_id}",
        json={"type": "broker"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["type"] == "broker"

    await api.delete(f"/api/v1/accounts/{acc_id}", headers=auth_headers)


async def test_create_account_with_number_and_duplicate_409(api, auth_headers):
    num = f"NUM-{uuid.uuid4().hex[:8]}"
    first = await api.post(
        "/api/v1/accounts",
        json={"name": "Nubank CPF", "type": "bank", "account_number": num},
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert first.json()["account_number"] == num

    dup = await api.post(
        "/api/v1/accounts",
        json={"name": "Outra", "type": "bank", "account_number": num},
        headers=auth_headers,
    )
    assert dup.status_code == 409
    await api.delete(f"/api/v1/accounts/{first.json()['id']}", headers=auth_headers)


async def test_create_account_rejects_invalid_type(api, auth_headers):
    resp = await api.post(
        "/api/v1/accounts",
        json={"name": "x", "type": "invalid"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_delete_account_blocked_when_has_transactions(api, auth_headers, pool):
    created = await api.post(
        "/api/v1/accounts",
        json={"name": f"acc-{uuid.uuid4().hex[:8]}", "type": "bank"},
        headers=auth_headers,
    )
    acc_id = created.json()["id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category) VALUES ($1, $2, $3, $4)",
            uuid.UUID(acc_id),
            date(2099, 6, 1),
            -10,
            "outros",
        )
    blocked = await api.delete(f"/api/v1/accounts/{acc_id}", headers=auth_headers)
    assert blocked.status_code == 409
    # remove a transação e então a conta deve sair
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", uuid.UUID(acc_id))
    ok = await api.delete(f"/api/v1/accounts/{acc_id}", headers=auth_headers)
    assert ok.status_code == 204
