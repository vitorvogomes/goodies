"""Tests for asset operations CRUD."""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient


@pytest.fixture
async def _cleanup_operations(pool: Any) -> None:
    """Clean up test operations and users after test."""
    yield
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM asset_operations WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'test_%_%@test.com')"
        )
        await conn.execute(
            "DELETE FROM users WHERE email LIKE 'test_%_%@test.com'"
        )


class TestCreateAssetOperation:
    """Test POST /asset-operations."""

    @pytest.mark.asyncio
    async def test_create_valid_operation(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with valid data returns 201 with created operation."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["asset_symbol"] == "PETR4"
        assert data["tipo"] == "compra"
        assert float(data["quantidade"]) == 10.0

    @pytest.mark.asyncio
    async def test_create_with_notes_and_external_id(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with optional notes and external_id."""
        payload = {
            "broker": "Binance",
            "asset_symbol": "BTC",
            "asset_category": "Cripto",
            "tipo": "compra",
            "quantidade": 0.5,
            "valor_unitario": 100000.00,
            "data_operacao": "2026-01-15",
            "notes": "Compra no bear market",
            "external_id": "binance_order_12345",
        }
        resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["notes"] == "Compra no bear market"
        assert data["external_id"] == "binance_order_12345"

    @pytest.mark.asyncio
    async def test_create_invalid_tipo_returns_422(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with invalid tipo returns 422."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "invalid_type",  # not in CHECK constraint
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zero_quantidade_returns_422(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with quantidade=0 returns 422."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 0.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_negative_valor_unitario_returns_422(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with negative valor_unitario returns 422."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": -25.50,
            "data_operacao": "2026-06-01",
        }
        resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_all_valid_tipos(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """POST with all valid tipos."""
        valid_tipos = ["compra", "venda", "dividendo", "juros", "aporte", "resgate"]
        for tipo in valid_tipos:
            payload = {
                "broker": "Test",
                "asset_symbol": "TEST",
                "asset_category": "Teste",
                "tipo": tipo,
                "quantidade": 1.0,
                "valor_unitario": 100.0,
                "data_operacao": "2026-06-01",
            }
            resp = await api.post(
                "/api/v1/asset-operations",
                json=payload,
                headers=auth_headers,
            )
            assert resp.status_code == 201, f"Failed for tipo={tipo}"


class TestListAssetOperations:
    """Test GET /asset-operations."""

    @pytest.mark.asyncio
    async def test_list_empty(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET returns empty list when no operations."""
        resp = await api.get(
            "/api/v1/asset-operations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_created_operations(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET returns created operations."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        create_resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        assert create_resp.status_code == 201

        list_resp = await api.get(
            "/api/v1/asset-operations",
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data) == 1
        assert data[0]["asset_symbol"] == "PETR4"

    @pytest.mark.asyncio
    async def test_list_filter_by_asset_symbol(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET with ?asset_symbol filter."""
        # Create 2 operations
        for symbol in ["PETR4", "VALE3"]:
            payload = {
                "broker": "B3",
                "asset_symbol": symbol,
                "asset_category": "Ações Nacionais",
                "tipo": "compra",
                "quantidade": 10.0,
                "valor_unitario": 25.50,
                "data_operacao": "2026-06-01",
            }
            await api.post(
                "/api/v1/asset-operations",
                json=payload,
                headers=auth_headers,
            )

        # Filter by PETR4
        resp = await api.get(
            "/api/v1/asset-operations?asset_symbol=PETR4",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["asset_symbol"] == "PETR4"

    @pytest.mark.asyncio
    async def test_list_filter_by_tipo(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET with ?tipo filter."""
        # Create operations with different tipos
        for tipo in ["compra", "venda"]:
            payload = {
                "broker": "B3",
                "asset_symbol": "PETR4",
                "asset_category": "Ações Nacionais",
                "tipo": tipo,
                "quantidade": 10.0,
                "valor_unitario": 25.50,
                "data_operacao": "2026-06-01",
            }
            await api.post(
                "/api/v1/asset-operations",
                json=payload,
                headers=auth_headers,
            )

        # Filter by venda
        resp = await api.get(
            "/api/v1/asset-operations?tipo=venda",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tipo"] == "venda"


class TestUpdateAssetOperation:
    """Test PUT /asset-operations/{id}."""

    @pytest.mark.asyncio
    async def test_update_valid_operation(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """PUT with valid data returns 200."""
        # Create
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        create_resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        op_id = create_resp.json()["id"]

        # Update
        update_payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 15.0,  # changed
            "valor_unitario": 26.00,  # changed
            "data_operacao": "2026-06-02",  # changed
        }
        resp = await api.put(
            f"/api/v1/asset-operations/{op_id}",
            json=update_payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["quantidade"]) == 15.0

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """PUT nonexistent operation returns 404."""
        fake_id = str(uuid.uuid4())
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        resp = await api.put(
            f"/api/v1/asset-operations/{fake_id}",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestDeleteAssetOperation:
    """Test DELETE /asset-operations/{id}."""

    @pytest.mark.asyncio
    async def test_delete_operation(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """DELETE returns 204."""
        # Create
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
        }
        create_resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        op_id = create_resp.json()["id"]

        # Delete
        resp = await api.delete(
            f"/api/v1/asset-operations/{op_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await api.get(
            f"/api/v1/asset-operations/{op_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """DELETE nonexistent operation returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await api.delete(
            f"/api/v1/asset-operations/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestGetAssetOperation:
    """Test GET /asset-operations/{id}."""

    @pytest.mark.asyncio
    async def test_get_operation(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET by id returns the operation."""
        payload = {
            "broker": "B3",
            "asset_symbol": "PETR4",
            "asset_category": "Ações Nacionais",
            "tipo": "compra",
            "quantidade": 10.0,
            "valor_unitario": 25.50,
            "data_operacao": "2026-06-01",
            "notes": "Test operation",
        }
        create_resp = await api.post(
            "/api/v1/asset-operations",
            json=payload,
            headers=auth_headers,
        )
        op_id = create_resp.json()["id"]

        resp = await api.get(
            f"/api/v1/asset-operations/{op_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == op_id
        assert data["asset_symbol"] == "PETR4"
        assert data["notes"] == "Test operation"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self, api: AsyncClient, auth_headers: dict, _cleanup_operations: None
    ) -> None:
        """GET nonexistent operation returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await api.get(
            f"/api/v1/asset-operations/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
