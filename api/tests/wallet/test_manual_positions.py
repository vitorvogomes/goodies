"""Story 7.8 — Ajustes › Posições manuais: carteira manual (SideSwap/Liquid) e DeFi numa lista com
a data informada e o vencimento; aviso de vencimento DeFi a 7 dias ou menos, com o `Alert` de
`common`."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from engines.common.alerts import Alert, AlertContext
from engines.common.month_status import month_status
from engines.wallet.defi import defi_maturity_provider


@pytest.mark.asyncio
async def test_manual_list_with_date_and_maturity(api, wallet_user: dict[str, Any]) -> None:
    h = wallet_user["headers"]
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-USDT", "quantity": 12.5, "as_of": "2026-09-30"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    r = await api.post(
        "/api/v1/defi/positions",
        json={
            "asset_symbol": "hyUSD",
            "balance": 3,
            "protocol": "hylo",
            "maturity_date": "2027-01-15",
        },
        headers=h,
    )
    assert r.status_code in (200, 201), r.text
    items = (await api.get("/api/v1/wallets/manual", headers=h)).json()
    wallet = next(i for i in items if i["kind"] == "carteira")
    assert (wallet["id"], wallet["as_of"], wallet["quantity"]) == (
        "liquid/L-USDT",
        "2026-09-30",
        12.5,
    )
    defi = next(i for i in items if i["kind"] == "defi")
    assert (defi["asset_symbol"], defi["maturity_date"], defi["protocol"]) == (
        "hyUSD",
        "2027-01-15",
        "hylo",
    )


@pytest.mark.asyncio
async def test_maturity_alert_within_7_days(pool, wallet_user: dict[str, Any]) -> None:
    today = date(2026, 10, 18)
    async with pool.acquire() as conn:
        for days, symbol in ((7, "PT-in"), (8, "PT-out"), (-1, "PT-gone")):
            await conn.execute(
                "INSERT INTO defi_positions (user_id, asset_symbol, balance, maturity_date) "
                "VALUES ($1::uuid, $2, 1, $3)",
                wallet_user["user_id"],
                symbol,
                today + timedelta(days=days),
            )
        ctx = AlertContext(
            today=today,
            periodo=today.replace(day=1),
            months=month_status(),
            owner_id=wallet_user["user_id"],
        )
        alerts = await defi_maturity_provider(conn, ctx)
    assert all(isinstance(a, Alert) for a in alerts)
    assert [a.message for a in alerts] == ["PT-in vence em 25/10/2026."]
    assert alerts[0].action.label == "Ver posições manuais"
    assert alerts[0].action.route == "/ajustes/posicoes-manuais"


@pytest.mark.asyncio
async def test_backdated_manual_position_rewrites_later_history(
    api, pool, wallet_user: dict[str, Any]
) -> None:
    """Revisão do Épico 7: informar para trás vale também para o histórico depois da data (senão o
    passado lê a quantidade antiga); data futura → 422."""
    h = wallet_user["headers"]
    url = "/api/v1/wallets/positions/manual"
    body = {"chain": "liquid", "asset_symbol": "L-BTC"}
    r = await api.post(url, json={**body, "quantity": 0.01, "as_of": "2001-10-10"}, headers=h)
    assert r.status_code == 200, r.text
    r = await api.post(url, json={**body, "quantity": 0.012, "as_of": "2001-10-01"}, headers=h)
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT h.ref_date, h.quantity FROM wallet_position_history h JOIN wallet_positions w "
            "ON w.asset_id = h.asset_id AND w.chain = h.chain "
            "AND w.wallet_address = h.wallet_address "
            "WHERE w.user_id = $1 AND w.is_manual AND w.asset_symbol = 'L-BTC' "
            "AND h.ref_date BETWEEN '2001-01-01' AND '2001-12-31' ORDER BY h.ref_date",
            wallet_user["user_id"],
        )
        await conn.execute(
            "DELETE FROM wallet_position_history "
            "WHERE ref_date BETWEEN '2001-01-01' AND '2001-12-31'"
        )
    assert [(str(r["ref_date"]), float(r["quantity"])) for r in rows] == [("2001-10-01", 0.012)]
    future = await api.post(url, json={**body, "quantity": 1, "as_of": "2999-01-01"}, headers=h)
    assert future.status_code == 422
