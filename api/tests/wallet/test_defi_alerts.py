"""Alertas de vencimento DeFi (30d/7d) — STORY-04-09. Pure fn + endpoint."""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from engines.wallet.defi import DefiMaturity, defi_maturity_alerts

_MAT = date(2026, 9, 29)  # xSOL/hyUSD


def _pos(maturity: date | None) -> DefiMaturity:
    return DefiMaturity(asset_symbol="xSOL", maturity_date=maturity, protocol="Phantom")


def test_no_alert_far_from_maturity() -> None:
    # hoje 06-06 → 115 dias p/ 09-29: fora das janelas (30/7)
    assert defi_maturity_alerts([_pos(_MAT)], date(2026, 6, 6)) == []


def test_warning_at_30_days() -> None:
    alerts = defi_maturity_alerts([_pos(_MAT)], date(2026, 8, 30))  # 30 dias
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"
    assert alerts[0].type == "defi_maturity"
    assert alerts[0].data["days_until"] == 30


def test_critical_at_7_days() -> None:
    alerts = defi_maturity_alerts([_pos(_MAT)], date(2026, 9, 22))  # 7 dias
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert alerts[0].data["days_until"] == 7


def test_critical_inside_7_days() -> None:
    alerts = defi_maturity_alerts([_pos(_MAT)], date(2026, 9, 25))  # 4 dias
    assert alerts[0].severity == "critical"


def test_past_maturity_and_no_date_skipped() -> None:
    positions = [_pos(_MAT), _pos(None)]
    assert defi_maturity_alerts(positions, date(2026, 10, 1)) == []  # vencida + sem data


@pytest.mark.asyncio
async def test_alerts_endpoint(api: httpx.AsyncClient, wallet_user: dict) -> None:
    h = wallet_user["headers"]
    # posição longe do vencimento → endpoint não dispara hoje (115 dias)
    await api.post(
        "/api/v1/defi/positions",
        json={"asset_symbol": "xSOL", "balance": 10, "maturity_date": "2026-09-29"},
        headers=h,
    )
    resp = await api.get("/api/v1/defi/alerts", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []  # nenhuma janela disparada hoje


@pytest.mark.asyncio
async def test_alerts_endpoint_requires_auth(api: httpx.AsyncClient) -> None:
    assert (await api.get("/api/v1/defi/alerts")).status_code == 401
