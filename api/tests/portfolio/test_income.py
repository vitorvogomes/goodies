"""Tests for STORY-02-10 — rendimentos (dividendo/juros) separados de ganho."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _op(
    api: AsyncClient, headers: dict, sym: str, category: str, tipo: str,
    qty: float, val: float, data: str = "2026-03-10",
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "B3",
            "asset_symbol": sym,
            "asset_category": category,
            "tipo": tipo,
            "quantidade": qty,
            "valor_unitario": val,
            "data_operacao": data,
        },
        headers=headers,
    )


class TestIncome:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/income")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_sum_by_asset_and_type(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Dividendo (FII) + juros (RF) → total + by_type breakdown."""
        await _op(api, auth_headers, "MXRF11", "FIIs", "dividendo", 1.0, 100.0)
        await _op(api, auth_headers, "RDB-NUB", "Renda Fixa", "juros", 1.0, 50.0)

        resp = await api.get("/api/v1/portfolio/income", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["total"]) - 150.0) < 0.01
        assert abs(float(data["by_type"]["dividendo"]) - 100.0) < 0.01
        assert abs(float(data["by_type"]["juros"]) - 50.0) < 0.01
        mxrf = next(a for a in data["by_asset"] if a["asset_symbol"] == "MXRF11")
        assert abs(float(mxrf["total"]) - 100.0) < 0.01

    @pytest.mark.asyncio
    async def test_excludes_capital_operations(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """compra/venda must NOT count as income (separa ganho de capital)."""
        await _op(api, auth_headers, "PETR4", "Ações Nacionais", "compra", 100.0, 10.0)
        await _op(api, auth_headers, "PETR4", "Ações Nacionais", "venda", 50.0, 15.0)
        await _op(api, auth_headers, "PETR4", "Ações Nacionais", "dividendo", 1.0, 30.0)

        resp = await api.get("/api/v1/portfolio/income", headers=auth_headers)
        data = resp.json()
        assert abs(float(data["total"]) - 30.0) < 0.01

    @pytest.mark.asyncio
    async def test_period_filter(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        await _op(
            api, auth_headers, "MXRF11", "FIIs", "dividendo", 1.0, 40.0,
            data="2026-01-10",
        )
        await _op(
            api, auth_headers, "MXRF11", "FIIs", "dividendo", 1.0, 60.0,
            data="2026-05-10",
        )
        resp = await api.get(
            "/api/v1/portfolio/income?from=2026-04-01&to=2026-06-30",
            headers=auth_headers,
        )
        data = resp.json()
        assert abs(float(data["total"]) - 60.0) < 0.01

    @pytest.mark.asyncio
    async def test_by_category(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        await _op(api, auth_headers, "MXRF11", "FIIs", "dividendo", 1.0, 40.0)
        await _op(api, auth_headers, "HFOF11", "FIIs", "dividendo", 1.0, 20.0)
        resp = await api.get("/api/v1/portfolio/income", headers=auth_headers)
        data = resp.json()
        fii = next(c for c in data["by_category"] if c["asset_category"] == "FIIs")
        assert abs(float(fii["total"]) - 60.0) < 0.01
