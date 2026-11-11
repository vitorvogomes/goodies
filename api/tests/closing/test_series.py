"""Story 9.3 — séries dos gráficos: do primeiro mês fechado até o período, uma por mês; mês sem
patrimônio coberto vira lacuna (None, sem interpolação); a média 12m do realizado vem da API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engines.closing import series as series_service
from engines.common.dates import today_brt

D = Decimal


@pytest.mark.asyncio
async def test_series_route_and_gap(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    mes = f"{today_brt():%Y-%m}"
    r = await api.get(f"/api/v1/closing/series?ate={mes}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    months = [p["month"][:7] for p in body["points"]]
    assert months == sorted(months) and (not months or months[-1] == mes)  # nunca depois
    month = date(2097, 3, 1)
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(
                "INSERT INTO month_closes (month, version, status, coverage) VALUES "
                "($1, 1, 'closed', '{\"B3\": \"patrimônio não coberto\"}')",
                month,
            )
            await conn.execute(
                "INSERT INTO month_summary_totals (month, version, as_of, patrimonio, aplicado, "
                "investido, taxa_poupanca) VALUES ($1, 1, '2097-03-31', 1000, 900, 50, 41.5)",
                month,
            )
            point = await series_service._point(conn, "x", month)
        finally:
            await tx.rollback()
    assert (point.patrimonio, point.aplicado, point.realizado) == (None, None, D(50))
    assert point.taxa_poupanca == D("41.50")  # v2.2: a linha da taxa de poupança
