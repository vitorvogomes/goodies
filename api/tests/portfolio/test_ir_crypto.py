"""Tests for STORY-02-12 — IR cripto: consolidação mensal de vendas + alerta 80%.

Isenção mensal R$ 35.000; alerta em 80% = R$ 28.000.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _op(
    api: AsyncClient, headers: dict, tipo: str, qty: float, val: float, data: str,
    sym: str = "BTC",
) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "Binance",
            "asset_symbol": sym,
            "asset_category": "Cripto",
            "tipo": tipo,
            "quantidade": qty,
            "valor_unitario": val,
            "data_operacao": data,
        },
        headers=headers,
    )


def _month(data: dict, ym: str) -> dict:
    return next(m for m in data["meses"] if m["mes"] == ym)


class TestCryptoIR:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/portfolio/ir-crypto")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_month_under_28k_no_alert(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Vendas 20k < 28k → isento, sem alerta, IR 0."""
        await _op(api, auth_headers, "compra", 2.0, 20000.0, "2026-01-05")
        await _op(api, auth_headers, "venda", 1.0, 20000.0, "2026-02-10")
        resp = await api.get("/api/v1/portfolio/ir-crypto", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        m = _month(data, "2026-02")
        assert abs(float(m["total_vendas"]) - 20000.0) < 0.01
        assert m["isento"] is True
        assert m["alerta"] is False
        assert float(m["ir_estimado"]) == 0.0

    @pytest.mark.asyncio
    async def test_month_28k_to_35k_alert_but_exempt(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Vendas 30k → alerta (>28k) mas isento (<35k), IR 0."""
        await _op(api, auth_headers, "compra", 2.0, 20000.0, "2026-01-05")
        await _op(api, auth_headers, "venda", 1.0, 30000.0, "2026-03-10")
        resp = await api.get("/api/v1/portfolio/ir-crypto", headers=auth_headers)
        data = resp.json()
        m = _month(data, "2026-03")
        assert abs(float(m["total_vendas"]) - 30000.0) < 0.01
        assert m["isento"] is True
        assert m["alerta"] is True
        assert float(m["ir_estimado"]) == 0.0

    @pytest.mark.asyncio
    async def test_month_over_35k_taxable(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Vendas 40k > 35k → tributável: ganho 20k x 15% = 3000."""
        await _op(api, auth_headers, "compra", 2.0, 20000.0, "2026-01-05")
        await _op(api, auth_headers, "venda", 1.0, 40000.0, "2026-04-10")
        resp = await api.get("/api/v1/portfolio/ir-crypto", headers=auth_headers)
        data = resp.json()
        m = _month(data, "2026-04")
        assert m["isento"] is False
        assert m["alerta"] is True
        # ganho = 1 * (40000 - 20000) = 20000 → IR 3000
        assert abs(float(m["ganho"]) - 20000.0) < 0.01
        assert abs(float(m["ir_estimado"]) - 3000.0) < 0.01

    @pytest.mark.asyncio
    async def test_exactly_35k_is_exempt(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Boundary: vendas == R$ 35.000 são ISENTAS (limite inclusivo)."""
        await _op(api, auth_headers, "compra", 2.0, 20000.0, "2026-01-05")
        await _op(api, auth_headers, "venda", 1.0, 35000.0, "2026-05-10")
        resp = await api.get("/api/v1/portfolio/ir-crypto", headers=auth_headers)
        m = _month(resp.json(), "2026-05")
        assert abs(float(m["total_vendas"]) - 35000.0) < 0.01
        assert m["isento"] is True
        assert float(m["ir_estimado"]) == 0.0

    @pytest.mark.asyncio
    async def test_thresholds_reported(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await api.get("/api/v1/portfolio/ir-crypto", headers=auth_headers)
        data = resp.json()
        assert abs(float(data["limite_isencao"]) - 35000.0) < 0.01
        assert abs(float(data["alerta_threshold"]) - 28000.0) < 0.01
        assert data["meses"] == []
