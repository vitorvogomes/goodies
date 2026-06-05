"""Tests for STORY-02-06 — GET /api/v1/portfolio/xirr (per-asset + consolidated)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


class TestXIRREndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        """No bearer token → 401/403."""
        resp = await api.get("/api/v1/portfolio/xirr")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_empty_portfolio(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """No operations → consolidated null, empty maps."""
        resp = await api.get("/api/v1/portfolio/xirr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["consolidated"] is None
        assert data["by_asset"] == {}
        assert data["by_category"] == {}
        assert "calculated_at" in data

    @pytest.mark.asyncio
    async def test_single_asset_with_current_price(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Buy 1y ago + current price → ~10% annualized."""
        # Buy 100 @ 10.00 = 1000 out, exactly 365 days ago
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 10.00,
                "data_operacao": _days_ago(365),
            },
            headers=auth_headers,
        )
        # Manual current price 11.00 → current value 1100 → XIRR ~10%
        await api.put(
            "/api/v1/portfolio/prices/PETR4",
            json={"price_brl": 11.00},
            headers=auth_headers,
        )

        resp = await api.get("/api/v1/portfolio/xirr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["consolidated"] is not None
        assert abs(data["consolidated"] - 0.10) < 0.01
        assert "PETR4" in data["by_asset"]
        assert abs(data["by_asset"]["PETR4"] - 0.10) < 0.01
        assert "Ações Nacionais" in data["by_category"]

    @pytest.mark.asyncio
    async def test_realized_only_without_price(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Buy then sell (realized), no current price → XIRR over realized flows."""
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "VALE3",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 10.00,
                "data_operacao": _days_ago(365),
            },
            headers=auth_headers,
        )
        # Sell everything today @ 11.00 → realized +1100
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "VALE3",
                "asset_category": "Ações Nacionais",
                "tipo": "venda",
                "quantidade": 100.0,
                "valor_unitario": 11.00,
                "data_operacao": _days_ago(0),
            },
            headers=auth_headers,
        )

        resp = await api.get("/api/v1/portfolio/xirr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # ~10% realized over 1 year, no price needed (qty_net=0)
        assert data["by_asset"]["VALE3"] is not None
        assert abs(data["by_asset"]["VALE3"] - 0.10) < 0.01

    @pytest.mark.asyncio
    async def test_by_category_aggregates_assets(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Two assets in same category → category XIRR present."""
        for sym in ("PETR4", "BBAS3"):
            await api.post(
                "/api/v1/asset-operations",
                json={
                    "broker": "B3",
                    "asset_symbol": sym,
                    "asset_category": "Ações Nacionais",
                    "tipo": "compra",
                    "quantidade": 100.0,
                    "valor_unitario": 10.00,
                    "data_operacao": _days_ago(365),
                },
                headers=auth_headers,
            )
            await api.put(
                f"/api/v1/portfolio/prices/{sym}",
                json={"price_brl": 11.00},
                headers=auth_headers,
            )

        resp = await api.get("/api/v1/portfolio/xirr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "Ações Nacionais" in data["by_category"]
        assert abs(data["by_category"]["Ações Nacionais"] - 0.10) < 0.01
        assert abs(data["consolidated"] - 0.10) < 0.01
