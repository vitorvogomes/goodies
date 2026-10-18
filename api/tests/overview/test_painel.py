"""Story 4.1 — GET /api/v1/overview/painel: KPIs em `Valued` (valor, motivo de ausência, as_of,
fonte, stale) a partir dos termos de ledger/calc e portfolio/calc."""

from __future__ import annotations

import pytest

from engines.common.dates import today_brt

URL = "/api/v1/overview/painel"
KPIS = ("resultado_mes", "patrimonio", "resultado_investimentos", "rentabilidade_nominal")


@pytest.mark.asyncio
async def test_current_month(api, auth_headers) -> None:
    periodo = f"{today_brt():%Y-%m}"
    r = await api.get(f"{URL}?periodo={periodo}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["periodo"] == periodo
    for k in KPIS:
        assert set(body[k]) >= {"value", "unavailable_reason", "as_of", "source", "stale"}
    res = body["resultado_mes"]
    assert res["source"] == "ledger" if res["value"] is not None else res["unavailable_reason"]
    assert body["patrimonio"]["source"] == "portfolio"


@pytest.mark.asyncio
async def test_past_month_comes_from_the_month_summary(api, auth_headers) -> None:
    """Desde a Story 5.2 o Painel lê o mês por `closing`: um mês passado é valorado na data."""
    body = (await api.get(f"{URL}?periodo=2025-01", headers=auth_headers)).json()
    assert body["patrimonio"]["value"] is not None
    assert body["patrimonio"]["source"] == "portfolio"


@pytest.mark.asyncio
async def test_bad_period_and_auth(api, auth_headers) -> None:
    assert (await api.get(f"{URL}?periodo=2026-13", headers=auth_headers)).status_code == 422
    assert (await api.get(f"{URL}?periodo=2026-10")).status_code == 401


def test_analytics_folder_is_gone() -> None:
    from pathlib import Path

    assert not (Path(__file__).parents[2] / "engines" / "analytics").exists()


@pytest.mark.asyncio
async def test_old_market_price_marks_stale(api, auth_headers, pool) -> None:
    """API de preço falhando: o Painel mostra o último valor marcado defasado, sem erro."""
    import uuid
    from datetime import timedelta

    from engines.common.owner import get_owner_id

    t = f"ZS{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'B3', $2, 'Ações Nacionais', 'compra', 1, 10, '2026-01-02')",
            owner,
            t,
        )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual, fetched_at) "
            "VALUES ($1, 11, 'brapi', false, now() - $2::interval)",
            t,
            timedelta(days=30),
        )
    try:
        body = (await api.get(f"{URL}?periodo={today_brt():%Y-%m}", headers=auth_headers)).json()
        assert body["patrimonio"]["value"] is not None
        assert body["patrimonio"]["stale"] is True
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", t)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", t)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{t}")
