"""CRUD de categorias (STORY-01-02) + seed default."""

import uuid


async def test_categories_requires_auth(api):
    resp = await api.get("/api/v1/categories")
    assert resp.status_code == 401


async def test_categories_seeded(api, auth_headers):
    resp = await api.get("/api/v1/categories", headers=auth_headers)
    assert resp.status_code == 200
    by_name = {c["name"]: c for c in resp.json()}
    # alguns defaults semeados pela migration 0004
    assert by_name["alimentação"]["kind"] == "expense"
    assert by_name["Flash Capital"]["kind"] == "income"


async def test_filter_categories_by_kind(api, auth_headers):
    resp = await api.get("/api/v1/categories?kind=income", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()
    assert all(c["kind"] == "income" for c in resp.json())


async def test_create_update_delete_category(api, auth_headers):
    name = f"cat-{uuid.uuid4().hex[:8]}"
    created = await api.post(
        "/api/v1/categories",
        json={"name": name, "kind": "expense"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert created.json()["is_active"] is True

    updated = await api.put(
        f"/api/v1/categories/{cid}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = await api.delete(f"/api/v1/categories/{cid}", headers=auth_headers)
    assert deleted.status_code == 204


async def test_create_category_rejects_invalid_kind(api, auth_headers):
    resp = await api.post(
        "/api/v1/categories",
        json={"name": "x", "kind": "bogus"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_create_category_rejects_duplicate_name(api, auth_headers):
    name = f"cat-{uuid.uuid4().hex[:8]}"
    first = await api.post(
        "/api/v1/categories", json={"name": name, "kind": "expense"}, headers=auth_headers
    )
    assert first.status_code == 201
    dup = await api.post(
        "/api/v1/categories", json={"name": name, "kind": "income"}, headers=auth_headers
    )
    assert dup.status_code == 409
    await api.delete(f"/api/v1/categories/{first.json()['id']}", headers=auth_headers)
