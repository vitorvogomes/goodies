"""CRUD de custos fixos (STORY-01-07)."""

import uuid


async def test_fixed_costs_requires_auth(api):
    resp = await api.get("/api/v1/fixed-costs")
    assert resp.status_code == 401


async def test_create_and_list_fixed_cost(api, auth_headers):
    name = f"Aluguel-{uuid.uuid4().hex[:8]}"
    created = await api.post(
        "/api/v1/fixed-costs",
        json={"name": name, "amount": 1500.0, "due_day": 5, "category": "moradia"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["amount"] == 1500.0
    assert body["due_day"] == 5
    assert body["is_active"] is True

    listed = await api.get("/api/v1/fixed-costs", headers=auth_headers)
    assert listed.status_code == 200
    assert any(fc["id"] == body["id"] for fc in listed.json())

    await api.delete(f"/api/v1/fixed-costs/{body['id']}", headers=auth_headers)


async def test_create_rejects_invalid_due_day(api, auth_headers):
    for bad in (0, 32):
        resp = await api.post(
            "/api/v1/fixed-costs",
            json={"name": "x", "amount": 10, "due_day": bad, "category": "outros"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


async def test_create_rejects_non_positive_amount(api, auth_headers):
    resp = await api.post(
        "/api/v1/fixed-costs",
        json={"name": "x", "amount": 0, "due_day": 5, "category": "outros"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_update_and_delete_fixed_cost(api, auth_headers):
    created = await api.post(
        "/api/v1/fixed-costs",
        json={
            "name": f"fc-{uuid.uuid4().hex[:8]}",
            "amount": 99,
            "due_day": 10,
            "category": "lazer",
        },
        headers=auth_headers,
    )
    fc_id = created.json()["id"]

    updated = await api.put(
        f"/api/v1/fixed-costs/{fc_id}",
        json={"amount": 120, "is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 120.0
    assert updated.json()["is_active"] is False

    deleted = await api.delete(f"/api/v1/fixed-costs/{fc_id}", headers=auth_headers)
    assert deleted.status_code == 204
    missing = await api.delete(f"/api/v1/fixed-costs/{fc_id}", headers=auth_headers)
    assert missing.status_code == 404


async def test_filter_active_fixed_costs(api, auth_headers):
    created = await api.post(
        "/api/v1/fixed-costs",
        json={
            "name": f"fc-{uuid.uuid4().hex[:8]}",
            "amount": 50,
            "due_day": 1,
            "category": "outros",
            "is_active": False,
        },
        headers=auth_headers,
    )
    fc_id = created.json()["id"]
    active_only = await api.get("/api/v1/fixed-costs?active=true", headers=auth_headers)
    assert all(fc["is_active"] for fc in active_only.json())
    assert not any(fc["id"] == fc_id for fc in active_only.json())
    await api.delete(f"/api/v1/fixed-costs/{fc_id}", headers=auth_headers)
