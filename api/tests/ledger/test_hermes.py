"""Endpoints Hermes (STORY-01-09): POST /hermes/expenses, /hermes/income.

Auth = service token scope=hermes (secret distinto do JWT de usuário). amount no
request é magnitude positiva; o endpoint aplica o sinal (despesa negativa).
"""

import uuid

from scripts.ops.gen_hermes_token import generate_hermes_token


def _hermes_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {generate_hermes_token()}"}


async def test_hermes_requires_token(api):
    resp = await api.post(
        "/api/v1/hermes/expenses",
        json={"account_id": str(uuid.uuid4()), "date": "2099-06-01", "amount": 10, "category": "x"},
    )
    assert resp.status_code == 401


async def test_hermes_rejects_user_token(api, auth_headers, account):
    # token de usuário (assinado com outro secret) não vale no Hermes
    resp = await api.post(
        "/api/v1/hermes/expenses",
        json={"account_id": account, "date": "2099-06-01", "amount": 50, "category": "alimentação"},
        headers=auth_headers,
    )
    assert resp.status_code == 401


async def test_hermes_register_expense_applies_negative_sign(api, account):
    resp = await api.post(
        "/api/v1/hermes/expenses",
        json={
            "account_id": account,
            "date": "2099-06-01",
            "amount": 50,
            "category": "alimentação",
            "description": "lanche",
        },
        headers=_hermes_headers(),
    )
    assert resp.status_code == 201
    assert resp.json()["amount"] == -50.0


async def test_hermes_register_income_positive(api, account):
    resp = await api.post(
        "/api/v1/hermes/income",
        json={"account_id": account, "date": "2099-06-01", "amount": 300, "category": "Extra"},
        headers=_hermes_headers(),
    )
    assert resp.status_code == 201
    assert resp.json()["amount"] == 300.0


async def test_hermes_unknown_account_returns_422(api):
    resp = await api.post(
        "/api/v1/hermes/income",
        json={"account_id": str(uuid.uuid4()), "date": "2099-06-01", "amount": 10, "category": "x"},
        headers=_hermes_headers(),
    )
    assert resp.status_code == 422


async def test_hermes_rejects_non_positive_amount(api, account):
    resp = await api.post(
        "/api/v1/hermes/expenses",
        json={"account_id": account, "date": "2099-06-01", "amount": 0, "category": "x"},
        headers=_hermes_headers(),
    )
    assert resp.status_code == 422


async def test_hermes_expense_respects_investment_category_kind(api, account, pool):
    # review m4→main: aporte lançado via Hermes numa categoria de investimento não pode
    # virar despesa de consumo (derrubaria a taxa de poupança). kind vem da categoria.
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories (name, kind) VALUES ('ZZHermesInv', 'investment') "
            "ON CONFLICT (name) DO NOTHING"
        )
    try:
        resp = await api.post(
            "/api/v1/hermes/expenses",
            json={
                "account_id": account,
                "date": "2099-06-02",
                "amount": 200,
                "category": "ZZHermesInv",
            },
            headers=_hermes_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["amount"] == -200.0
        async with pool.acquire() as conn:
            kind = await conn.fetchval(
                "SELECT kind FROM transactions WHERE id = $1", uuid.UUID(resp.json()["id"])
            )
        assert kind == "investment"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions WHERE category = 'ZZHermesInv'")
            await conn.execute("DELETE FROM categories WHERE name = 'ZZHermesInv'")
