"""Fold do sleeve cripto em Posições → Alocação/Rebalanceamento (m4, Fase 3).

Cripto entra nas Posições como linhas POR ATIVO (qtd + preço atual + valor, fiéis) com
custo/preço médio/resultado = None (custo é conhecido só no nível do sleeve). Isso faz a
Alocação e o Rebalanceamento incluírem Cripto automaticamente. Tickers sintéticos.
"""
from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def _price(conn: Any, ticker: str, brl: float) -> None:
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ($1, $2, 'coingecko', false)",
        ticker, brl,
    )


async def _wallet(conn: Any, uid: str, chain: str, sym: str, qty: float) -> None:
    await conn.execute(
        "INSERT INTO wallet_positions "
        "(user_id, chain, wallet_address, asset_symbol, quantity, source, is_manual) "
        "VALUES ($1, $2, $3, $4, $5, 'etherscan', false)",
        uid, chain, f"addr-{chain}", sym, qty,
    )


async def _defi(conn: Any, uid: str, sym: str, bal: float) -> None:
    await conn.execute(
        "INSERT INTO defi_positions (user_id, protocol, asset_symbol, balance, is_active) "
        "VALUES ($1, 'hylo', $2, $3, true)",
        uid, sym, bal,
    )


async def _b3_buy(api: AsyncClient, headers: dict, sym: str, qty: float, price: float) -> None:
    await api.post(
        "/api/v1/asset-operations",
        json={
            "broker": "B3", "asset_symbol": sym, "asset_category": "Ações Nacionais",
            "tipo": "compra", "quantidade": qty, "valor_unitario": price,
            "data_operacao": "2026-01-02",
        },
        headers=headers,
    )
    await api.post(f"/api/v1/market/prices/{sym}", json={"price_brl": price}, headers=headers)


class TestPositionsCryptoFold:
    @pytest.mark.asyncio
    async def test_crypto_row_has_null_cost(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        headers, uid = portfolio_user["headers"], portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 2.0)
        resp = await api.get("/api/v1/portfolio/positions", headers=headers)
        assert resp.status_code == 200
        pos = next(p for p in resp.json() if p["asset_symbol"] == "TKNA")
        assert pos["asset_category"] == "Cripto"
        assert abs(float(pos["quantidade_net"]) - 2.0) < 1e-9
        assert abs(float(pos["preco_atual"]) - 100.0) < 0.01
        assert abs(float(pos["valor_atual"]) - 200.0) < 0.01
        assert pos["preco_medio"] is None
        assert pos["custo_total"] is None
        assert pos["resultado"] is None
        assert pos["resultado_pct"] is None

    @pytest.mark.asyncio
    async def test_crypto_aggregated_by_symbol(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        """Mesmo ativo em 3 chains → 1 linha agregada (detalhe por-chain fica na aba Carteiras)."""
        headers, uid = portfolio_user["headers"], portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "XETH", 10.0)
            await _wallet(conn, uid, "ethereum", "XETH", 1.0)
            await _wallet(conn, uid, "arbitrum", "XETH", 0.5)
            await _wallet(conn, uid, "binance", "XETH", 0.5)
        resp = await api.get("/api/v1/portfolio/positions", headers=headers)
        rows = [p for p in resp.json() if p["asset_symbol"] == "XETH"]
        assert len(rows) == 1
        assert abs(float(rows[0]["quantidade_net"]) - 2.0) < 1e-9
        assert abs(float(rows[0]["valor_atual"]) - 20.0) < 0.01

    @pytest.mark.asyncio
    async def test_crypto_defi_included(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        headers, uid = portfolio_user["headers"], portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKND", 4.0)
            await _defi(conn, uid, "TKND", 25.0)  # 100
        resp = await api.get("/api/v1/portfolio/positions", headers=headers)
        pos = next(p for p in resp.json() if p["asset_symbol"] == "TKND")
        assert pos["asset_category"] == "Cripto"
        assert abs(float(pos["valor_atual"]) - 100.0) < 0.01


class TestAllocationCryptoFold:
    @pytest.mark.asyncio
    async def test_allocation_includes_cripto(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        headers, uid = portfolio_user["headers"], portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 1.0)  # 100
        resp = await api.get("/api/v1/portfolio/allocation", headers=headers)
        assert resp.status_code == 200
        cats = {c["category"]: c for c in resp.json()["categories"]}
        assert "Cripto" in cats
        assert cats["Cripto"]["valor_atual"] > 0
        assert cats["Cripto"]["pct_meta"] == 5.0
        assert cats["Cripto"]["desvio_pp"] is not None


class TestRebalancingCryptoFold:
    @pytest.mark.asyncio
    async def test_rebalancing_includes_cripto_when_below_target(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        """B3=1000, cripto=10 → Cripto ~1% < meta 5% → recebe aporte."""
        headers, uid = portfolio_user["headers"], portfolio_user["user_id"]
        await _b3_buy(api, headers, "XPTO", 100.0, 10.0)  # 1000 em Ações Nacionais
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 0.1)  # 10
        resp = await api.get(
            "/api/v1/portfolio/rebalancing?amount=1000", headers=headers
        )
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]
        assert "Cripto" in suggestions
        assert suggestions["Cripto"] > 0
