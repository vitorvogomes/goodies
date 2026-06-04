"""Endpoint de alertas compute-on-read (STORY-01-08)."""

import datetime


async def test_alerts_requires_auth(api):
    resp = await api.get("/api/v1/cashflow/alerts")
    assert resp.status_code == 401


async def test_alerts_lists_upcoming_fixed_cost(api, auth_headers):
    today = datetime.date.today()
    due_soon = (today + datetime.timedelta(days=2)).day
    fc = await api.post(
        "/api/v1/fixed-costs",
        json={"name": "Aluguel-alert", "amount": 1500, "due_day": due_soon, "category": "moradia"},
        headers=auth_headers,
    )
    assert fc.status_code == 201

    resp = await api.get("/api/v1/cashflow/alerts", headers=auth_headers)
    assert resp.status_code == 200
    due = [a for a in resp.json() if a["type"] == "fixed_cost_due"]
    assert any(a["data"]["name"] == "Aluguel-alert" for a in due)
    # custo fixo limpo pela fixture autouse _clean_fixed_costs
