"""Alocação atual vs meta (`service.calculate_allocation`, STORY-02-08; a rota v1
/api/v1/portfolio/allocation saiu na Story 10.6)."""

from __future__ import annotations

from typing import Any

import pytest

from engines.portfolio import service
from tests.portfolio.conftest import add_op, run, set_price


async def _buy_with_price(uid: str, sym: str, category: str, qty: float, price: float) -> None:
    await add_op(uid, sym, qty, price, category=category)
    await set_price(sym, price)


def _cat(data: dict, name: str) -> dict:
    return next(c for c in data["categories"] if c["category"] == name)


class TestAllocation:
    @pytest.mark.asyncio
    async def test_targets_only_no_positions(
        self, pool: Any, portfolio_user: dict[str, Any]
    ) -> None:
        """No positions but targets seeded → pct_atual 0, desvio = -meta."""
        uid = portfolio_user["user_id"]
        data = await run(pool, service.calculate_allocation, uid)
        assert data["total"] == 0
        rf = _cat(data, "Renda Fixa")
        assert abs(float(rf["pct_meta"]) - 50.0) < 0.01
        assert float(rf["pct_atual"]) == 0.0
        assert abs(float(rf["desvio_pp"]) - (-50.0)) < 0.01

    @pytest.mark.asyncio
    async def test_allocation_sums_to_100(
        self, pool: Any, portfolio_user: dict[str, Any]
    ) -> None:
        """pct_atual across categories sums to ~100%."""
        uid = portfolio_user["user_id"]
        # RF 5000, Ações 5000 → 50/50
        await _buy_with_price(uid, "Flash_CDB", "Renda Fixa", 1.0, 5000.0)
        await _buy_with_price(uid, "PETR4", "Ações Nacionais", 100.0, 50.0)

        data = await run(pool, service.calculate_allocation, uid)
        assert abs(float(data["total"]) - 10000.0) < 0.01
        total_pct = sum(float(c["pct_atual"]) for c in data["categories"])
        assert abs(total_pct - 100.0) < 0.01

    @pytest.mark.asyncio
    async def test_deviation_calc(self, pool: Any, portfolio_user: dict[str, Any]) -> None:
        """RF at 50% actual vs 50% target → desvio ~0; Ações 50% vs 10% → +40pp."""
        uid = portfolio_user["user_id"]
        await _buy_with_price(uid, "Flash_CDB", "Renda Fixa", 1.0, 5000.0)
        await _buy_with_price(uid, "PETR4", "Ações Nacionais", 100.0, 50.0)

        data = await run(pool, service.calculate_allocation, uid)
        rf = _cat(data, "Renda Fixa")
        acoes = _cat(data, "Ações Nacionais")
        assert abs(float(rf["desvio_pp"]) - 0.0) < 0.01
        assert abs(float(acoes["desvio_pp"]) - 40.0) < 0.01

    @pytest.mark.asyncio
    async def test_category_without_target(
        self, pool: Any, portfolio_user: dict[str, Any]
    ) -> None:
        """Position in a category with no target → pct_meta/desvio null."""
        uid = portfolio_user["user_id"]
        # Classe fora das 6 é recusada (Story 3.2); "sem meta" = classe canônica sem linha de meta.
        await pool.execute(
            "DELETE FROM portfolio_targets WHERE user_id = $1 AND category = 'ETFs'",
            portfolio_user["user_id"],
        )
        await _buy_with_price(uid, "WEIRD11", "ETFs", 10.0, 100.0)
        data = await run(pool, service.calculate_allocation, uid)
        weird = _cat(data, "ETFs")
        assert weird["pct_meta"] is None
        assert weird["desvio_pp"] is None
        assert abs(float(weird["pct_atual"]) - 100.0) < 0.01
