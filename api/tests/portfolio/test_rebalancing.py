"""Tests for STORY-02-09 — motor de rebalanceamento.

Unit tests on the pure function suggest_rebalancing + integration on the endpoint.
"""
from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from engines.portfolio.service import suggest_rebalancing


class TestSuggestRebalancingPure:
    def test_proportional_to_negative_gap(self) -> None:
        """Distributes contribution proportionally to under-target gaps."""
        value_by_cat = {"Cripto": 1000.0}
        targets = {
            "Ações Nacionais": 10.0,
            "Aposentadoria": 12.5,
            "Cripto": 5.0,
            "ETFs": 12.5,
            "FIIs": 10.0,
            "Renda Fixa": 50.0,
        }
        sug = suggest_rebalancing(value_by_cat, targets, 4000.0)
        # total = 5000; Cripto gap = 250-1000 <0 → excluded
        assert "Cripto" not in sug
        assert abs(sum(sug.values()) - 4000.0) < 0.01
        # Renda Fixa gap 2500 is largest → biggest slice
        assert abs(sug["Renda Fixa"] - 4000.0 * 2500.0 / 4750.0) < 0.01

    def test_never_suggests_for_over_target(self) -> None:
        """Single over-target category → empty suggestions (no sell)."""
        sug = suggest_rebalancing({"Cripto": 1000.0}, {"Cripto": 5.0}, 10.0)
        assert sug == {}

    def test_zero_contribution_empty(self) -> None:
        sug = suggest_rebalancing({"Renda Fixa": 100.0}, {"Renda Fixa": 50.0}, 0.0)
        assert sug == {}


async def _buy_with_price(
    api: AsyncClient, headers: dict, sym: str, category: str,
    qty: float, price: float,
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "X",
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


class TestRebalancingEndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/rebalancing?amount=4500")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_crypto_over_target_gets_zero(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        """Cripto above target → no aporte; others split the contribution."""
        headers = portfolio_user["headers"]
        await _buy_with_price(api, headers, "BTC", "Cripto", 1.0, 1000.0)

        resp = await api.get(
            "/api/v1/portfolio/rebalancing?amount=4000", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["contribution"]) - 4000.0) < 0.01
        assert "Cripto" not in data["suggestions"]
        assert abs(sum(float(v) for v in data["suggestions"].values()) - 4000.0) < 0.01
        assert "Cripto" in data["target_allocation"]

    @pytest.mark.asyncio
    async def test_zero_amount_returns_message(
        self, api: AsyncClient, portfolio_user: dict[str, Any]
    ) -> None:
        headers = portfolio_user["headers"]
        await _buy_with_price(api, headers, "BTC", "Cripto", 1.0, 1000.0)
        resp = await api.get(
            "/api/v1/portfolio/rebalancing?amount=0", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == {}
        assert "message" in data
