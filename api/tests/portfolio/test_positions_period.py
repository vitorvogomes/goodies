"""Story 7.1 — Posições em dois níveis: classe → ativo com aplicado e valor atual no fim do mês e o
resultado do período da leitura (mês, tri, ano, início); preço desatualizado/ausente/manual
marcado; `closing.build_period_summary` soma os meses (fechado do snapshot, aberto ao vivo) e
nunca passa do período."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import service as closing
from engines.common.owner import get_owner_id
from engines.portfolio import calc

D = Decimal


def test_period_result_term() -> None:
    # fim 180, início 120, aportes do período 28, proventos 5 → 37
    assert calc.period_result(D(180), D(120), flows=D(28), income=D(5)) == D(37)


async def _seed(conn: Any, ticker: str) -> None:
    owner = await get_owner_id(conn)
    for tipo, qty, unit, d in (
        ("compra", 10, 10, date(2025, 1, 15)),
        ("compra", 2, 14, date(2025, 2, 10)),
        ("dividendo", 1, 5, date(2025, 2, 20)),
    ):
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, 'Ações Nacionais', "
            "$3, $4, $5, $6)",
            owner,
            ticker,
            tipo,
            qty,
            unit,
            d,
        )
    for d, price in ((date(2025, 1, 31), 12), (date(2025, 2, 28), 15)):
        await conn.execute(
            "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source) "
            "VALUES ($1, $2, $3, 'brapi')",
            ticker,
            d,
            price,
        )


async def _drop(conn: Any, ticker: str) -> None:
    await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", ticker)
    await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{ticker}")


@pytest.mark.asyncio
async def test_positions_by_reading(pool: Any) -> None:
    import main  # noqa: F401

    t = f"ZQ{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        await _seed(conn, t)
        try:
            mes = await closing.positions(conn, "2025-02", "mes")
            inicio = await closing.positions(conn, "2025-02", "inicio")
        finally:
            await _drop(conn, t)

    def asset(report: Any) -> Any:
        cls = next(c for c in report.classes if c.key == "acoes_br")
        return next(a for a in cls.assets if a.symbol == t)

    a = asset(mes)
    assert (a.aplicado, a.valor.value) == (D("128.00"), D("180.00"))
    assert a.resultado == D("37.00")  # 180 − 120 − 28 + 5
    b = asset(inicio)
    assert (b.aplicado, b.valor.value) == (D("128.00"), D("180.00"))  # mesmo fim de mês
    assert b.resultado == D("57.00")  # 180 − 128 + 5
    assert [m.month for m in mes.months] == [date(2025, 2, 1)]
    assert inicio.months[0].month == date(2024, 7, 1)
    assert inicio.months[-1].month == date(2025, 2, 1)  # nunca depois do período
    assert all(m.source in ("live", "snapshot") for m in inicio.months)
    order = [c.key for c in mes.classes]
    assert order == ["acoes_br", "etfs", "fiis", "renda_fixa", "aposentadoria", "cripto"]
    crypto = mes.classes[-1]
    assert crypto.is_bucket and crypto.label == "Bloco cripto: quanto saiu × quanto vale"
    assert all(x.aplicado is None and x.resultado is None for x in crypto.assets)


@pytest.mark.asyncio
async def test_period_summary_sums_months(pool: Any) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        months = [date(2025, 1, 1), date(2025, 2, 1)]
        period = await closing.build_period_summary(conn, months)
        each = [await closing.month_summary(conn, m) for m in months]
    assert period.gastos == sum((s.gastos for s in each), D(0))
    assert period.receitas == sum((s.receitas for s in each), D(0))
    assert [(m.month, m.source) for m in period.months] == [(s.month, s.source) for s in each]


@pytest.mark.asyncio
async def test_price_flags_live(pool: Any) -> None:
    """Mês corrente: preço velho → "preço de dd/mm/aaaa" (stale); sem preço → sem_preco; manual."""
    import main  # noqa: F401
    from engines.common.dates import today_brt

    t_old, t_none, t_man = (f"Z{x}{uuid.uuid4().hex[:2].upper()}3" for x in "ABC")
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        for t in (t_old, t_none, t_man):
            await conn.execute(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                "tipo, quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, "
                "'Ações Nacionais', 'compra', 1, 10, '2025-01-10')",
                owner,
                t,
            )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual, fetched_at) "
            "VALUES ($1, 11, 'brapi', false, now() - interval '10 days')",
            t_old,
        )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ($1, 12, 'manual', true)",
            t_man,
        )
        try:
            report = await closing.positions(conn, f"{today_brt():%Y-%m}", "mes")
        finally:
            for t in (t_old, t_none, t_man):
                await _drop(conn, t)
    rows = {a.symbol: a for c in report.classes for a in c.assets}
    assert rows[t_old].valor.stale and rows[t_old].valor.as_of is not None
    assert rows[t_none].valor.value is None
    assert rows[t_none].valor.unavailable_reason == "sem_preco"
    assert rows[t_man].manual is True
