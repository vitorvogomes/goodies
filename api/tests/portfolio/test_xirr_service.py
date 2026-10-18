"""XIRR por ativo, classe e consolidado (`service.calculate_portfolio_xirr`, STORY-02-06; a rota v1
/api/v1/portfolio/xirr saiu na Story 10.6 — o Painel e a Rentabilidade leem pelo mesmo serviço)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from engines.portfolio import service
from tests.portfolio.conftest import add_op, run, set_price


def _days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


class TestXIRRService:
    @pytest.mark.asyncio
    async def test_empty_portfolio(self, pool: Any, user_id: str) -> None:
        """No operations → consolidated null, empty maps."""
        data = await run(pool, service.calculate_portfolio_xirr, user_id)
        assert data["consolidated"] is None
        assert data["by_asset"] == {}
        assert data["by_category"] == {}
        assert "calculated_at" in data

    @pytest.mark.asyncio
    async def test_single_asset_with_current_price(
        self, pool: Any, user_id: str) -> None:
        """Buy 1y ago + current price → ~10% annualized."""
        # Buy 100 @ 10.00 = 1000 out, exactly 365 days ago
        await add_op(user_id, "PETR4", 100.0, 10.00, day=_days_ago(365))
        # Manual current price 11.00 → current value 1100 → XIRR ~10%
        await set_price("PETR4", 11.00)

        data = await run(pool, service.calculate_portfolio_xirr, user_id)
        assert data["consolidated"] is not None
        assert abs(data["consolidated"] - 0.10) < 0.01
        assert "PETR4" in data["by_asset"]
        assert abs(data["by_asset"]["PETR4"] - 0.10) < 0.01
        assert "Ações Nacionais" in data["by_category"]

    @pytest.mark.asyncio
    async def test_realized_only_without_price(self, pool: Any, user_id: str) -> None:
        """Buy then sell (realized), no current price → XIRR over realized flows."""
        await add_op(user_id, "VALE3", 100.0, 10.00, day=_days_ago(365))
        # Sell everything today @ 11.00 → realized +1100
        await add_op(user_id, "VALE3", 100.0, 11.00, tipo="venda", day=_days_ago(0))

        data = await run(pool, service.calculate_portfolio_xirr, user_id)
        # ~10% realized over 1 year, no price needed (qty_net=0)
        assert data["by_asset"]["VALE3"] is not None
        assert abs(data["by_asset"]["VALE3"] - 0.10) < 0.01

    @pytest.mark.asyncio
    async def test_by_category_aggregates_assets(
        self, pool: Any, user_id: str) -> None:
        """Two assets in same category → category XIRR present."""
        for sym in ("PETR4", "BBAS3"):
            await add_op(user_id, sym, 100.0, 10.00, day=_days_ago(365))
            await set_price(sym, 11.00)

        data = await run(pool, service.calculate_portfolio_xirr, user_id)
        assert "Ações Nacionais" in data["by_category"]
        assert abs(data["by_category"]["Ações Nacionais"] - 0.10) < 0.01
        assert abs(data["consolidated"] - 0.10) < 0.01
