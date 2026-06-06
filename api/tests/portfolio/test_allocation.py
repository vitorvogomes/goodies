"""Tests for STORY-02-08 — GET /api/v1/portfolio/allocation (atual vs meta)."""
from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def _buy_with_price(
    api: AsyncClient, headers: dict, sym: str, category: str,
    qty: float, price: float,
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "B3",
            "asset_symbol": sym,
            "asset_category": category,
            "tipo": "compra",
            "quantidade": qty,
            "valor_unitario": price,
            "data_operacao": "2026-01-02",
        },
        headers=headers,
    )
    await api.post(
        f"/api/v1/market/prices/{sym}",
        json={"price_brl": price},
        headers=headers,
    )


def _cat(data: dict, name: str) -> dict:
    return next(c for c in data["categories"] if c["category"] == name)


class TestAllocation:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/allocation")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_targets_only_no_positions(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        """No positions but targets seeded → pct_atual 0, desvio = -meta."""
        headers = portfolio_user["headers"]
        resp = await api.get("/api/v1/portfolio/allocation", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        rf = _cat(data, "Renda Fixa")
        assert abs(float(rf["pct_meta"]) - 50.0) < 0.01
        assert float(rf["pct_atual"]) == 0.0
        assert abs(float(rf["desvio_pp"]) - (-50.0)) < 0.01

    @pytest.mark.asyncio
    async def test_allocation_sums_to_100(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        """pct_atual across categories sums to ~100%."""
        headers = portfolio_user["headers"]
        # RF 5000, Ações 5000 → 50/50
        await _buy_with_price(api, headers, "Flash_CDB", "Renda Fixa", 1.0, 5000.0)
        await _buy_with_price(api, headers, "PETR4", "Ações Nacionais", 100.0, 50.0)

        resp = await api.get("/api/v1/portfolio/allocation", headers=headers)
        data = resp.json()
        assert abs(float(data["total"]) - 10000.0) < 0.01
        total_pct = sum(float(c["pct_atual"]) for c in data["categories"])
        assert abs(total_pct - 100.0) < 0.01

    @pytest.mark.asyncio
    async def test_deviation_calc(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        """RF at 50% actual vs 50% target → desvio ~0; Ações 50% vs 10% → +40pp."""
        headers = portfolio_user["headers"]
        await _buy_with_price(api, headers, "Flash_CDB", "Renda Fixa", 1.0, 5000.0)
        await _buy_with_price(api, headers, "PETR4", "Ações Nacionais", 100.0, 50.0)

        resp = await api.get("/api/v1/portfolio/allocation", headers=headers)
        data = resp.json()
        rf = _cat(data, "Renda Fixa")
        acoes = _cat(data, "Ações Nacionais")
        assert abs(float(rf["desvio_pp"]) - 0.0) < 0.01
        assert abs(float(acoes["desvio_pp"]) - 40.0) < 0.01

    @pytest.mark.asyncio
    async def test_category_without_target(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        """Position in a category with no target → pct_meta/desvio null."""
        headers = portfolio_user["headers"]
        await _buy_with_price(
            api, headers, "WEIRD1", "Categoria Sem Meta", 10.0, 100.0
        )
        resp = await api.get("/api/v1/portfolio/allocation", headers=headers)
        data = resp.json()
        weird = _cat(data, "Categoria Sem Meta")
        assert weird["pct_meta"] is None
        assert weird["desvio_pp"] is None
        assert abs(float(weird["pct_atual"]) - 100.0) < 0.01
