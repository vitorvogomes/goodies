"""CRUD de transações + validação + filtros/paginação (STORY-01-03)."""

import uuid


async def test_transactions_requires_auth(api):
    resp = await api.get("/api/v1/transactions")
    assert resp.status_code == 401


async def test_create_transaction(api, auth_headers, account):
    resp = await api.post(
        "/api/v1/transactions",
        json={
            "account_id": account,
            "date": "2099-03-10",
            "amount": -123.45,
            "category": "alimentação",
            "description": "mercado",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == -123.45
    assert body["category"] == "alimentação"
    assert body["is_recurring"] is False


async def test_create_rejects_zero_amount(api, auth_headers, account):
    resp = await api.post(
        "/api/v1/transactions",
        json={"account_id": account, "date": "2099-03-10", "amount": 0, "category": "x"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_unknown_account(api, auth_headers):
    resp = await api.post(
        "/api/v1/transactions",
        json={
            "account_id": str(uuid.uuid4()),
            "date": "2099-03-10",
            "amount": -10,
            "category": "x",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_list_filters_and_pagination(api, auth_headers, account):
    # 3 transações em 2099-04, categorias e datas distintas
    payloads = [
        {"date": "2099-04-01", "amount": 1000, "category": "Salário"},
        {"date": "2099-04-10", "amount": -200, "category": "alimentação"},
        {"date": "2099-04-20", "amount": -50, "category": "transporte"},
    ]
    for p in payloads:
        r = await api.post(
            "/api/v1/transactions",
            json={"account_id": account, **p},
            headers=auth_headers,
        )
        assert r.status_code == 201

    # filtro por conta + categoria
    by_cat = await api.get(
        f"/api/v1/transactions?account_id={account}&category=alimentação",
        headers=auth_headers,
    )
    assert by_cat.status_code == 200
    assert by_cat.json()["total"] == 1
    assert by_cat.json()["items"][0]["category"] == "alimentação"

    # filtro por intervalo de datas
    by_range = await api.get(
        f"/api/v1/transactions?account_id={account}&from=2099-04-05&to=2099-04-15",
        headers=auth_headers,
    )
    assert by_range.json()["total"] == 1
    assert by_range.json()["items"][0]["date"] == "2099-04-10"

    # paginação
    page = await api.get(
        f"/api/v1/transactions?account_id={account}&limit=2&offset=0",
        headers=auth_headers,
    )
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2


async def test_update_and_delete_transaction(api, auth_headers, account):
    created = await api.post(
        "/api/v1/transactions",
        json={"account_id": account, "date": "2099-05-01", "amount": -10, "category": "outros"},
        headers=auth_headers,
    )
    tx_id = created.json()["id"]

    updated = await api.put(
        f"/api/v1/transactions/{tx_id}",
        json={"amount": -25, "category": "lazer"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == -25
    assert updated.json()["category"] == "lazer"

    deleted = await api.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert deleted.status_code == 204
    missing = await api.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert missing.status_code == 404
