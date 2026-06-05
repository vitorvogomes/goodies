"""Tests for STORY-02-11 — estimativa de IR por categoria de renda variável."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _buy_with_price(
    api: AsyncClient, headers: dict, sym: str, category: str,
    qty: float, buy: float, current: float,
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "B3",
            "asset_symbol": sym,
            "asset_category": category,
            "tipo": "compra",
            "quantidade": qty,
            "valor_unitario": buy,
            "data_operacao": "2026-01-02",
        },
        headers=headers,
    )
    await api.put(
        f"/api/v1/portfolio/prices/{sym}",
        json={"price_brl": current},
        headers=headers,
    )


def _cat(data: dict, name: str) -> dict:
    return next(c for c in data["categories"] if c["category"] == name)


class TestIREstimate:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/ir-estimate")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_gain_times_aliquota_acoes(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Ações: ganho 200 x 0.15 = 30."""
        await _buy_with_price(
            api, auth_headers, "PETR4", "Ações Nacionais", 100.0, 10.0, 12.0
        )
        resp = await api.get("/api/v1/portfolio/ir-estimate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        acoes = _cat(data, "Ações Nacionais")
        assert abs(float(acoes["ganho"]) - 200.0) < 0.01
        assert abs(float(acoes["aliquota"]) - 0.15) < 0.001
        assert abs(float(acoes["ir_estimado"]) - 30.0) < 0.01
        assert abs(float(data["total_ir"]) - 30.0) < 0.01

    @pytest.mark.asyncio
    async def test_loss_zero_ir(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Prejuízo → IR 0 (não negativo)."""
        await _buy_with_price(
            api, auth_headers, "VALE3", "Ações Nacionais", 100.0, 10.0, 8.0
        )
        resp = await api.get("/api/v1/portfolio/ir-estimate", headers=auth_headers)
        data = resp.json()
        vale = _cat(data, "Ações Nacionais")
        assert float(vale["ir_estimado"]) == 0.0

    @pytest.mark.asyncio
    async def test_fii_aliquota_20(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """FII: ganho 100 x 0.20 = 20."""
        await _buy_with_price(
            api, auth_headers, "MXRF11", "FIIs", 100.0, 10.0, 11.0
        )
        resp = await api.get("/api/v1/portfolio/ir-estimate", headers=auth_headers)
        data = resp.json()
        fii = _cat(data, "FIIs")
        assert abs(float(fii["aliquota"]) - 0.20) < 0.001
        assert abs(float(fii["ir_estimado"]) - 20.0) < 0.01

    @pytest.mark.asyncio
    async def test_excludes_non_rv_categories(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """RF e Cripto não entram na estimativa de IR de RV."""
        await _buy_with_price(
            api, auth_headers, "Flash_CDB", "Renda Fixa", 1.0, 1000.0, 1100.0
        )
        await _buy_with_price(
            api, auth_headers, "BTC", "Cripto", 1.0, 1000.0, 1500.0
        )
        resp = await api.get("/api/v1/portfolio/ir-estimate", headers=auth_headers)
        data = resp.json()
        cats = {c["category"] for c in data["categories"]}
        assert "Renda Fixa" not in cats
        assert "Cripto" not in cats
