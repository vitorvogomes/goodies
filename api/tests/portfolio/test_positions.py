"""Posições atuais por ativo (`service.calculate_positions`, STORY-02-07; a rota v1
/api/v1/portfolio/positions saiu na Story 10.6 — as Posições da v2 leem pelo mesmo serviço)."""

from __future__ import annotations

from typing import Any

import pytest

from engines.portfolio import service
from tests.portfolio.conftest import add_op, run, set_price


async def _positions(pool: Any, uid: str) -> list[dict[str, Any]]:
    return await run(pool, service.calculate_positions, uid)


class TestPositions:
    @pytest.mark.asyncio
    async def test_empty(self, pool: Any, user_id: str) -> None:
        assert await _positions(pool, user_id) == []

    @pytest.mark.asyncio
    async def test_position_with_price(self, pool: Any, user_id: str) -> None:
        """Buy 100 @ 10, current price 12 → result +200 (20%)."""
        await add_op(user_id, "PETR4", 100.0, 10.0)
        await set_price("PETR4", 12.0)
        pos = next(p for p in await _positions(pool, user_id) if p["asset_symbol"] == "PETR4")
        assert float(pos["quantidade_net"]) == 100.0
        assert abs(float(pos["preco_medio"]) - 10.0) < 0.01
        assert abs(float(pos["custo_total"]) - 1000.0) < 0.01
        assert abs(float(pos["preco_atual"]) - 12.0) < 0.01
        assert abs(float(pos["valor_atual"]) - 1200.0) < 0.01
        assert abs(float(pos["resultado"]) - 200.0) < 0.01
        assert abs(float(pos["resultado_pct"]) - 20.0) < 0.01
        assert pos["stale"] is False
        assert pos["is_manual"] is True  # preço definido manualmente (editável)

    @pytest.mark.asyncio
    async def test_position_without_price_is_stale(self, pool: Any, user_id: str) -> None:
        """No manual price → valor_atual null, stale true (ADR-004)."""
        await add_op(user_id, "VALE3", 50.0, 80.0)
        pos = next(p for p in await _positions(pool, user_id) if p["asset_symbol"] == "VALE3")
        assert pos["stale"] is True
        assert pos["valor_atual"] is None
        assert pos["resultado"] is None
        # cost basis still known
        assert abs(float(pos["custo_total"]) - 4000.0) < 0.01
        assert pos["is_manual"] is True  # sem preço ainda → editável (default)

    @pytest.mark.asyncio
    async def test_position_auto_price_is_not_manual(self, pool: Any, user_id: str) -> None:
        """Preço capturado via Market Engine (is_manual=false) → posição is_manual=false."""
        await add_op(user_id, "WEGE3", 10.0, 30.0)
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
                "VALUES ('WEGE3', 35.0, 'brapi', false)"
            )
        pos = next(p for p in await _positions(pool, user_id) if p["asset_symbol"] == "WEGE3")
        assert pos["is_manual"] is False
        assert pos["stale"] is False
        assert abs(float(pos["preco_atual"]) - 35.0) < 0.01

    @pytest.mark.asyncio
    async def test_net_quantity_after_sell(self, pool: Any, user_id: str) -> None:
        """Buy 100 @ 10, sell 40 @ 15 → net 60, DCA still 10."""
        await add_op(user_id, "ITSA4", 100.0, 10.0)
        await add_op(user_id, "ITSA4", 40.0, 15.0, tipo="venda")
        await set_price("ITSA4", 12.0)
        pos = next(p for p in await _positions(pool, user_id) if p["asset_symbol"] == "ITSA4")
        assert float(pos["quantidade_net"]) == 60.0
        assert abs(float(pos["preco_medio"]) - 10.0) < 0.01
        assert abs(float(pos["custo_total"]) - 600.0) < 0.01
        assert abs(float(pos["valor_atual"]) - 720.0) < 0.01

    @pytest.mark.asyncio
    async def test_fully_sold_excluded(self, pool: Any, user_id: str) -> None:
        """Buy 100, sell 100 → net 0 → not listed as position."""
        await add_op(user_id, "BBAS3", 100.0, 10.0)
        await add_op(user_id, "BBAS3", 100.0, 12.0, tipo="venda")
        assert "BBAS3" not in {p["asset_symbol"] for p in await _positions(pool, user_id)}

    @pytest.mark.asyncio
    async def test_rf_aporte_position(self, pool: Any, user_id: str) -> None:
        """RF modeled as qty=1, valor=total; current price = valor atual base."""
        await add_op(user_id, "Flash_CDB", 1.0, 12000.0, tipo="aporte", category="Renda Fixa")
        await set_price("Flash_CDB", 13207.62)
        pos = next(p for p in await _positions(pool, user_id) if p["asset_symbol"] == "Flash_CDB")
        assert float(pos["quantidade_net"]) == 1.0
        assert abs(float(pos["valor_atual"]) - 13207.62) < 0.01
        assert abs(float(pos["resultado"]) - 1207.62) < 0.01
