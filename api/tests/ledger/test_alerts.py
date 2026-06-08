"""Endpoint de alertas compute-on-read (STORY-01-08)."""

import datetime
from decimal import Decimal
from typing import Any


def _month_back(cur: datetime.date, n: int) -> datetime.date:
    y, m = cur.year, cur.month - n
    while m < 1:
        m += 12
        y -= 1
    return datetime.date(y, m, 5)


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


async def test_overspend_excludes_investment(api: Any, auth_headers: dict, pool: Any) -> None:
    """Aportar mais num investimento (Binance) NÃO é overspend; só consumo (expense) é."""
    today = datetime.date.today()
    cur = datetime.date(today.year, today.month, 5)
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ('alert-kind', 'bank') RETURNING id"
        )

        async def _tx(d: datetime.date, amt: str, cat: str, kind: str, ext: str) -> None:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, kind, "
                "description, external_id) VALUES ($1,$2,$3,$4,$5,'x',$6)",
                acc, d, Decimal(amt), cat, kind, ext,
            )

        # pico de investimento no mês atual vs ~0 antes -> alertaria se não filtrasse kind
        await _tx(cur, "-1000", "ZZBinance", "investment", "i-cur")
        # pico de consumo no mês atual -> DEVE alertar
        await _tx(cur, "-1000", "ZZViagem", "expense", "e-cur")
        for n in (1, 2, 3):
            await _tx(_month_back(cur, n), "-10", "ZZBinance", "investment", f"i-{n}")
            await _tx(_month_back(cur, n), "-10", "ZZViagem", "expense", f"e-{n}")

    resp = await api.get("/api/v1/cashflow/alerts", headers=auth_headers)
    cats = {
        a["data"]["category"]
        for a in resp.json()
        if a["type"] == "category_overspend"
    }
    assert "ZZBinance" not in cats  # investimento fora do overspend
    assert "ZZViagem" in cats  # consumo dentro

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
