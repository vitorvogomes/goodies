"""Story 9.2 — crescimento do patrimônio = aporte + resultado (aporte = o aplicado que entrou;
proventos no resultado), as duas pontas da mesma fonte; o ativo de melhor desempenho; antes do
primeiro mês fechado ou sem o consolidado B3 → indisponível com o motivo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import growth as growth_service

D = Decimal


async def _closed(
    conn: Any, month: date, invested: int, applied: int, covered: bool = True
) -> None:
    coverage = "{}" if covered else '{"B3": "patrimônio não coberto"}'
    await conn.execute(
        "INSERT INTO month_closes (month, version, status, coverage) VALUES ($1, 1, 'closed', $2)",
        month,
        coverage,
    )
    await conn.execute(
        "INSERT INTO month_summary_totals (month, version, as_of, valor_investido, aplicado) "
        "VALUES ($1, 1, $2, $3, $4)",
        month,
        month.replace(day=28),
        invested,
        applied,
    )


@pytest.mark.asyncio
async def test_growth_from_snapshots(pool) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await _closed(conn, date(2097, 1, 1), 1000, 900)
            await _closed(conn, date(2097, 2, 1), 1300, 1100)
            await _closed(conn, date(2097, 3, 1), 1400, 1150, covered=False)
            feb = await growth_service.growth(conn, "2097-02", "mes")
            mar = await growth_service.growth(conn, "2097-03", "mes")
            before = await growth_service.growth(conn, "2097-01", "mes")
        finally:
            await tx.rollback()
    assert (feb.available, feb.start_value, feb.end_value) == (True, D(1000), D(1300))
    assert (feb.crescimento, feb.aporte, feb.resultado) == (D(300), D(200), D(100))
    assert (mar.available, mar.reason) == (False, "patrimonio_nao_coberto")
    assert (before.available, before.reason) == (False, "antes_do_primeiro_fechamento")
    rates = [a.xirr_mensal for a in feb.assets]
    assert rates == sorted(rates, reverse=True)
    if rates:
        assert feb.best is not None and feb.best.xirr_mensal == rates[0]
        if len([r for r in rates if r is not None]) > 1:
            assert feb.worst is not None and feb.worst.xirr_mensal == min(
                r for r in rates if r is not None
            )


@pytest.mark.asyncio
async def test_route(api, auth_headers) -> None:
    r = await api.get("/api/v1/closing/growth?periodo=2024-07&leitura=mes", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False and body["crescimento"] is None
