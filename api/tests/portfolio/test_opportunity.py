"""v2.2 — oportunidade nos aportes: os três sinais (3 meses, preço médio, máxima de 52 semanas) e o
fator limitado entre 0,75 e 1,25."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.portfolio.opportunity import (
    Signals,
    factor,
    market_signals,
    reference_day,
    signals,
)

D = Decimal


def test_neutral_without_data() -> None:
    assert factor(Signals()) == D(1)


def test_down_assets_weigh_more_and_highs_weigh_less_within_limits() -> None:
    down = factor(Signals(var_3m=D(-15), vs_pm=D(-10), dd_52w=D(-20)))
    assert D(1) < down < D("1.25")
    crash = factor(Signals(var_3m=D(-60), vs_pm=D(-50), dd_52w=D(-70)))
    assert crash == D("1.25")  # limite
    top = factor(Signals(var_3m=D(40), vs_pm=D(80), dd_52w=D(0)))
    assert top == D("0.75")
    assert factor(Signals(var_3m=D(10), dd_52w=D(-5))) < D(1)  # sem preço médio (cripto)


def test_reference_day_is_month_start_never_future() -> None:
    """Review v2.2: os sinais do mês são os do 1º dia dele — a divisão não muda a cada pregão."""
    from datetime import date

    assert reference_day(date(2026, 11, 1), date(2026, 11, 20)) == date(2026, 11, 1)
    assert reference_day(date(2026, 9, 1), date(2026, 11, 20)) == date(2026, 9, 1)
    assert reference_day(date(2026, 12, 1), date(2026, 11, 20)) == date(2026, 11, 20)


def test_missing_signal_renormalizes() -> None:
    assert factor(Signals(var_3m=D(-30))) == D("1.25")  # só ele: −30% leva ao limite


def test_signals_from_prices() -> None:
    s = signals(D(80), D(100), D(120), D(90))
    assert (s.var_3m, s.vs_pm, s.dd_52w) == (D("-20.00"), D("-11.11"), D("-33.33"))
    assert signals(D(80), None, None, None) == Signals()


@pytest.mark.asyncio
async def test_market_signals_from_history(pool: Any) -> None:
    t = f"ZOP{uuid.uuid4().hex[:3].upper()}"
    today = today_brt()
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        try:
            await conn.execute(
                "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
                "VALUES ($1, 80, 'brapi', false)",
                t,
            )
            await conn.execute(
                "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, is_manual) "
                "VALUES ($1, $2, 100, 'b3_cotahist', false), ($1, $3, 120, 'b3_cotahist', false), "
                "($1, $4, 90, 'b3_cotahist', false)",
                t,
                today - timedelta(days=300),
                today - timedelta(days=200),
                today - timedelta(days=95),
            )
            await conn.execute(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                "tipo, quantidade, valor_unitario, data_operacao) VALUES "
                "($1, 'B3', $2, 'Ações Nacionais', 'compra', 10, 100, $3)",
                owner,
                t,
                today - timedelta(days=300),
            )
            got = await market_signals(conn, owner, [t, "SEM-PRECO"], today)
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", t)
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", t)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", t)
    s = got[t]
    assert s.var_3m == D("-11.11")  # 80 × 90 (o último até 90 dias atrás)
    assert s.vs_pm == D("-20.00")  # 80 × 100
    assert s.dd_52w == D("-33.33")  # 80 × 120
    assert "SEM-PRECO" not in got
