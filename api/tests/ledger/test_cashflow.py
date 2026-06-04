"""Saldo running + resumo mensal + taxa de poupança (STORY-01-04 / 01-05).

A view monthly_summary agrega por mês globalmente; usamos meses 2099 únicos e
filtramos por mês para asserts determinísticos. A fixture `account` limpa as
transações ao fim.
"""


async def _post_tx(api, headers, account, date, amount, category):
    return await api.post(
        "/api/v1/transactions",
        json={"account_id": account, "date": date, "amount": amount, "category": category},
        headers=headers,
    )


async def test_cashflow_requires_auth(api):
    resp = await api.get("/api/v1/cashflow/summary")
    assert resp.status_code == 401


async def test_summary_savings_rate_for_month(api, auth_headers, account):
    # receita 10000, despesa 4500 -> taxa 55% (STORY-01-05).
    await _post_tx(api, auth_headers, account, "2099-07-01", 10000, "Salário")
    await _post_tx(api, auth_headers, account, "2099-07-15", -4500, "alimentação")

    resp = await api.get("/api/v1/cashflow/summary?month=2099-07", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["month"] == "2099-07"
    assert body["total_income"] == 10000.0
    assert body["total_expense"] == 4500.0
    assert body["net_cashflow"] == 5500.0
    assert abs(body["savings_rate"] - 55.0) < 0.01


async def test_summary_zero_income_returns_error(api, auth_headers, account):
    await _post_tx(api, auth_headers, account, "2099-08-10", -300, "transporte")
    resp = await api.get("/api/v1/cashflow/summary?month=2099-08", headers=auth_headers)
    assert resp.status_code == 422


async def test_summary_unknown_month_returns_404(api, auth_headers):
    resp = await api.get("/api/v1/cashflow/summary?month=2099-09", headers=auth_headers)
    assert resp.status_code == 404


async def test_summary_list_contains_month(api, auth_headers, account):
    await _post_tx(api, auth_headers, account, "2099-07-01", 8000, "Salário")
    resp = await api.get("/api/v1/cashflow/summary", headers=auth_headers)
    assert resp.status_code == 200
    months = {m["month"] for m in resp.json()}
    assert "2099-07" in months


async def test_cashflow_running_balance(api, auth_headers, account):
    await _post_tx(api, auth_headers, account, "2099-10-01", 1000, "Salário")
    await _post_tx(api, auth_headers, account, "2099-10-05", -200, "alimentação")
    await _post_tx(api, auth_headers, account, "2099-10-09", -50, "transporte")

    resp = await api.get(f"/api/v1/cashflow?account_id={account}", headers=auth_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 3
    # ordenado por data; running_balance acumulado
    assert entries[0]["running_balance"] == 1000.0
    assert entries[1]["running_balance"] == 800.0
    assert entries[2]["running_balance"] == 750.0
