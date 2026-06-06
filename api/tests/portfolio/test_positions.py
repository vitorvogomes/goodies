"""Tests for STORY-02-07 — GET /api/v1/portfolio/positions (preço manual)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _buy(
    api: AsyncClient, headers: dict, sym: str, qty: float, price: float,
    *, tipo: str = "compra", category: str = "Ações Nacionais",
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "B3",
            "asset_symbol": sym,
            "asset_category": category,
            "tipo": tipo,
            "quantidade": qty,
            "valor_unitario": price,
            "data_operacao": "2026-01-02",
        },
        headers=headers,
    )


class TestPositions:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/positions")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_empty(self, api: AsyncClient, auth_headers: dict) -> None:
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_position_with_price(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Buy 100 @ 10, current price 12 → result +200 (20%)."""
        await _buy(api, auth_headers, "PETR4", 100.0, 10.0)
        await api.post(
            "/api/v1/market/prices/PETR4",
            json={"price_brl": 12.0},
            headers=auth_headers,
        )
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        assert resp.status_code == 200
        pos = next(p for p in resp.json() if p["asset_symbol"] == "PETR4")
        assert float(pos["quantidade_net"]) == 100.0
        assert abs(float(pos["preco_medio"]) - 10.0) < 0.01
        assert abs(float(pos["custo_total"]) - 1000.0) < 0.01
        assert abs(float(pos["preco_atual"]) - 12.0) < 0.01
        assert abs(float(pos["valor_atual"]) - 1200.0) < 0.01
        assert abs(float(pos["resultado"]) - 200.0) < 0.01
        assert abs(float(pos["resultado_pct"]) - 20.0) < 0.01
        assert pos["stale"] is False

    @pytest.mark.asyncio
    async def test_position_without_price_is_stale(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """No manual price → valor_atual null, stale true (ADR-004)."""
        await _buy(api, auth_headers, "VALE3", 50.0, 80.0)
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        assert resp.status_code == 200
        pos = next(p for p in resp.json() if p["asset_symbol"] == "VALE3")
        assert pos["stale"] is True
        assert pos["valor_atual"] is None
        assert pos["resultado"] is None
        # cost basis still known
        assert abs(float(pos["custo_total"]) - 4000.0) < 0.01

    @pytest.mark.asyncio
    async def test_net_quantity_after_sell(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Buy 100 @ 10, sell 40 @ 15 → net 60, DCA still 10."""
        await _buy(api, auth_headers, "ITSA4", 100.0, 10.0)
        await _buy(api, auth_headers, "ITSA4", 40.0, 15.0, tipo="venda")
        await api.post(
            "/api/v1/market/prices/ITSA4",
            json={"price_brl": 12.0},
            headers=auth_headers,
        )
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        pos = next(p for p in resp.json() if p["asset_symbol"] == "ITSA4")
        assert float(pos["quantidade_net"]) == 60.0
        assert abs(float(pos["preco_medio"]) - 10.0) < 0.01
        assert abs(float(pos["custo_total"]) - 600.0) < 0.01
        assert abs(float(pos["valor_atual"]) - 720.0) < 0.01

    @pytest.mark.asyncio
    async def test_fully_sold_excluded(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Buy 100, sell 100 → net 0 → not listed as position."""
        await _buy(api, auth_headers, "BBAS3", 100.0, 10.0)
        await _buy(api, auth_headers, "BBAS3", 100.0, 12.0, tipo="venda")
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        symbols = {p["asset_symbol"] for p in resp.json()}
        assert "BBAS3" not in symbols

    @pytest.mark.asyncio
    async def test_rf_aporte_position(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """RF modeled as qty=1, valor=total; current price = valor atual base."""
        await _buy(
            api, auth_headers, "Flash_CDB", 1.0, 12000.0,
            tipo="aporte", category="Renda Fixa",
        )
        await api.post(
            "/api/v1/market/prices/Flash_CDB",
            json={"price_brl": 13207.62},
            headers=auth_headers,
        )
        resp = await api.get("/api/v1/portfolio/positions", headers=auth_headers)
        pos = next(p for p in resp.json() if p["asset_symbol"] == "Flash_CDB")
        assert float(pos["quantidade_net"]) == 1.0
        assert abs(float(pos["valor_atual"]) - 13207.62) < 0.01
        assert abs(float(pos["resultado"]) - 1207.62) < 0.01
