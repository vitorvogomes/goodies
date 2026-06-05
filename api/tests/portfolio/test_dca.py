"""Tests for DCA (Dollar Cost Averaging) — preço médio ponderado."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestDCAByAsset:
    """Test GET /api/v1/asset-operations/dca/{asset_symbol}."""

    @pytest.mark.asyncio
    async def test_dca_single_compra(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Single compra: DCA should equal valor_unitario."""
        # Create single compra
        create_resp = await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 25.50,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201

        # Get DCA
        resp = await api.get(
            "/api/v1/asset-operations/dca/PETR4",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_symbol"] == "PETR4"
        assert abs(float(data["preco_medio"]) - 25.50) < 0.01
        assert float(data["quantidade_total"]) == 100.0

    @pytest.mark.asyncio
    async def test_dca_multiple_compras_weighted_average(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Multiple compras: DCA = SUM(qty*price) / SUM(qty)."""
        # Compra 100 @ 20.00 = 2000
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 20.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Compra 50 @ 26.00 = 1300
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 50.0,
                "valor_unitario": 26.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        # DCA = (2000 + 1300) / (100 + 50) = 3300 / 150 = 22.00
        resp = await api.get(
            "/api/v1/asset-operations/dca/PETR4",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 22.00) < 0.01
        assert float(data["quantidade_total"]) == 150.0

    @pytest.mark.asyncio
    async def test_dca_ignores_venda(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Venda should not affect DCA (not included in calculation)."""
        # Compra 100 @ 25.50
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 25.50,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Venda 50 @ 30.00 (higher price, but shouldn't affect DCA)
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "venda",
                "quantidade": 50.0,
                "valor_unitario": 30.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        # DCA should still be 25.50 (only compra counted)
        resp = await api.get(
            "/api/v1/asset-operations/dca/PETR4",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 25.50) < 0.01
        assert float(data["quantidade_total"]) == 100.0

    @pytest.mark.asyncio
    async def test_dca_ignores_dividendo(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Dividendo should not affect DCA (not a cost basis)."""
        # Compra 100 @ 25.00
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 25.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Dividendo (quantidade não importa, é rendimento)
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "dividendo",
                "quantidade": 1.0,
                "valor_unitario": 50.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        resp = await api.get(
            "/api/v1/asset-operations/dca/PETR4",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 25.00) < 0.01

    @pytest.mark.asyncio
    async def test_dca_ignores_juros(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Juros should not affect DCA (interest yield, not cost)."""
        # Aporte 1000 @ 100.00 (RF scenario)
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "aporte",
                "quantidade": 1000.0,
                "valor_unitario": 100.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Juros (shouldn't affect)
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "juros",
                "quantidade": 1.0,
                "valor_unitario": 50.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        resp = await api.get(
            "/api/v1/asset-operations/dca/RDB-NUB",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 100.00) < 0.01

    @pytest.mark.asyncio
    async def test_dca_aporte_included(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Aporte tipo should be included in DCA calculation."""
        # Aporte 1000 @ 100.00
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "aporte",
                "quantidade": 1000.0,
                "valor_unitario": 100.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Aporte 500 @ 110.00
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "aporte",
                "quantidade": 500.0,
                "valor_unitario": 110.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        # DCA = (1000*100 + 500*110) / (1000 + 500) = 155000 / 1500 = 103.33
        resp = await api.get(
            "/api/v1/asset-operations/dca/RDB-NUB",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 103.33) < 0.01
        assert float(data["quantidade_total"]) == 1500.0

    @pytest.mark.asyncio
    async def test_dca_ignores_resgate(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Resgate should not affect DCA (exit, opposite of aporte)."""
        # Aporte 1000 @ 100.00
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "aporte",
                "quantidade": 1000.0,
                "valor_unitario": 100.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # Resgate 200 @ 110.00 (shouldn't affect DCA)
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "Nubank",
                "asset_symbol": "RDB-NUB",
                "asset_category": "Renda Fixa",
                "tipo": "resgate",
                "quantidade": 200.0,
                "valor_unitario": 110.00,
                "data_operacao": "2026-06-15",
            },
            headers=auth_headers,
        )

        resp = await api.get(
            "/api/v1/asset-operations/dca/RDB-NUB",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert abs(float(data["preco_medio"]) - 100.00) < 0.01
        assert float(data["quantidade_total"]) == 1000.0

    @pytest.mark.asyncio
    async def test_dca_not_found_returns_404(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """Asset with no compra/aporte operations returns 404."""
        resp = await api.get(
            "/api/v1/asset-operations/dca/NONEXISTENT",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestDCAAll:
    """Test GET /api/v1/asset-operations/dca (all assets)."""

    @pytest.mark.asyncio
    async def test_dca_all_returns_list(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """GET /dca returns list of all assets with DCA."""
        # PETR4: 100 @ 25.50
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 100.0,
                "valor_unitario": 25.50,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )
        # VALE3: 50 @ 80.00
        await api.post(
            "/api/v1/asset-operations",
            json={
                "broker": "B3",
                "asset_symbol": "VALE3",
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 50.0,
                "valor_unitario": 80.00,
                "data_operacao": "2026-06-01",
            },
            headers=auth_headers,
        )

        resp = await api.get(
            "/api/v1/asset-operations/dca",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        symbols = {d["asset_symbol"] for d in data}
        assert "PETR4" in symbols
        assert "VALE3" in symbols

        petr = next(d for d in data if d["asset_symbol"] == "PETR4")
        assert abs(float(petr["preco_medio"]) - 25.50) < 0.01

    @pytest.mark.asyncio
    async def test_dca_all_empty(
        self, api: AsyncClient, auth_headers: dict
    ) -> None:
        """GET /dca with no operations returns empty list."""
        resp = await api.get(
            "/api/v1/asset-operations/dca",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0
