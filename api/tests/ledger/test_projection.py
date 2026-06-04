"""Projeção de caixa 30/60/90 (STORY-01-06).

Projecao = saldo atual + receitas recorrentes previstas - custos fixos previstos,
escalados por no de meses no horizonte (30->1, 60->2, 90->3). Scoping por account_id
torna o saldo/recorrencia deterministicos no teste; o custo fixo eh limpo pela
fixture autouse _clean_fixed_costs.
"""


async def _post_tx(api, headers, account, date, amount, category, is_recurring=False):
    return await api.post(
        "/api/v1/transactions",
        json={
            "account_id": account,
            "date": date,
            "amount": amount,
            "category": category,
            "is_recurring": is_recurring,
        },
        headers=headers,
    )


async def test_projection_requires_auth(api):
    resp = await api.get("/api/v1/cashflow/projection")
    assert resp.status_code == 401


async def test_projection_30_60_90(api, auth_headers, account):
    # saldo atual = 5000 (recorrente) - 1000 = 4000; receita recorrente mensal = 5000
    await _post_tx(api, auth_headers, account, "2099-01-01", 5000, "Salário", is_recurring=True)
    await _post_tx(api, auth_headers, account, "2099-01-02", -1000, "alimentação")
    fc = await api.post(
        "/api/v1/fixed-costs",
        json={"name": "Aluguel-proj", "amount": 1500, "due_day": 5, "category": "moradia"},
        headers=auth_headers,
    )

    resp = await api.get(
        f"/api/v1/cashflow/projection?account_id={account}", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_balance"] == 4000.0
    assert data["monthly_income"] == 5000.0
    assert data["monthly_expenses"] == 1500.0

    points = {p["days"]: p for p in data["projections"]}
    assert points[30]["fixed_income"] == 5000.0
    assert points[30]["fixed_expenses"] == 1500.0
    assert points[30]["projected_balance"] == 7500.0  # 4000 + 5000 - 1500
    assert points[60]["projected_balance"] == 11000.0  # 4000 + 10000 - 3000
    assert points[90]["projected_balance"] == 14500.0  # 4000 + 15000 - 4500
    assert fc.status_code == 201  # custo fixo limpo pela fixture autouse
