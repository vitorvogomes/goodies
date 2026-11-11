"""Story 5.2 — resumo do mês ao vivo (`closing.build_month_summary`): termos da AD-7, as_of = fim
do mês (ou hoje), e a valoração de um mês passado pelo consolidado daquele fim de mês, pelo
histórico de preço até a data, ou nada (sem o preço de hoje)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import service as closing
from engines.common.dates import today_brt
from engines.common.owner import get_owner_id

MARCH = date(2026, 3, 1)


async def _buy(conn: Any, owner: str, ticker: str) -> None:
    await conn.execute(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
        "quantidade, valor_unitario, data_operacao) "
        "VALUES ($1, 'B3', $2, 'Ações Nacionais', 'compra', 7, 8, '2026-02-10')",
        owner,
        ticker,
    )


async def _drop(conn: Any, ticker: str) -> None:
    await conn.execute(
        "DELETE FROM broker_position_snapshots s USING assets a "
        "WHERE a.id = s.asset_id AND a.key = $1",
        f"b3:{ticker}",
    )
    await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", ticker)
    await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{ticker}")


@pytest.mark.asyncio
async def test_past_month_uses_the_consolidado_then_price_history(pool: Any) -> None:
    t = f"ZP{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await _buy(conn, owner, t)
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ($1, 99, 'brapi', false)",
            t,
        )  # o preço de hoje nunca vale para março
        try:
            none = await closing.build_month_summary(conn, MARCH)
            assert t not in none.valor_por_ativo and none.portfolio_stale
            await conn.execute(
                "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source) "
                "VALUES ($1, '2026-03-20', 9, 'brapi')",
                t,
            )
            hist = await closing.build_month_summary(conn, MARCH)
            assert hist.valor_por_ativo[t] == Decimal("63.00")
            asset = await conn.fetchval("SELECT id FROM assets WHERE key = $1", f"b3:{t}")
            await conn.execute(
                "INSERT INTO broker_position_snapshots "
                "(ref_date, asset_id, quantity, reported_value) VALUES ('2026-03-31', $1, 7, 70)",
                asset,
            )
            snap = await closing.build_month_summary(conn, MARCH)
            assert snap.valor_por_ativo[t] == Decimal("70.00")
            assert snap.coverage["B3"] == "consolidado de 31/03/2026"
            assert snap.as_of == date(2026, 3, 31)
            assert snap.valor_por_classe["acoes_br"] >= Decimal("70.00")
        finally:
            await _drop(conn, t)


@pytest.mark.asyncio
async def test_current_month_is_live_and_consistent(pool: Any) -> None:
    async with pool.acquire() as conn:
        s = await closing.build_month_summary(conn, today_brt().replace(day=1))
    assert s.as_of == today_brt()
    assert s.patrimonio == s.valor_investido + s.saldo_contas
    assert s.resultado_mes == s.receitas - s.gastos - s.investido


@pytest.mark.asyncio
async def test_summary_route(api, auth_headers) -> None:
    r = await api.get("/api/v1/closing/months/2026-03/summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["as_of"] == "2026-03-31"
    assert (
        await api.get("/api/v1/closing/months/2026-13/summary", headers=auth_headers)
    ).status_code == 422


@pytest.mark.asyncio
async def test_frozen_month_gets_real_return_once_ipca_is_out(pool) -> None:
    """Revisão do Épico 7: fechado antes de o IPCA do mês sair, a real congelou nula; na leitura,
    com o IPCA publicado, ela sai da nominal congelada (sem reabrir)."""
    month = date(2097, 1, 1)
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(
                "INSERT INTO month_closes (month, version, status) VALUES ($1, 1, 'closed')", month
            )
            await conn.execute(
                "INSERT INTO month_summary_totals (month, version, as_of, rentabilidade_mes, "
                "unavailable) VALUES ($1, 1, '2097-01-31', 12, "
                '\'{"rentabilidade_mes_real": "aguardando_ipca"}\')',
                month,
            )
            waiting = await closing.month_summary(conn, month)
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('IPCA', $1, 0.5, 'bcb')",
                month,
            )
            out = await closing.month_summary(conn, month)
        finally:
            await tx.rollback()
    assert waiting.source == "snapshot" and waiting.rentabilidade_mes_real is None
    assert waiting.unavailable["rentabilidade_mes_real"] == "aguardando_ipca"
    assert out.rentabilidade_mes_real is not None and out.rentabilidade_mes_real < Decimal(12)
    assert "rentabilidade_mes_real" not in out.unavailable


@pytest.mark.asyncio
async def test_real_since_start_estimates_missing_ipca_with_last_published(pool) -> None:
    """v2.2: o Painel não fica em "Aguardando o IPCA" — o mês sem IPCA usa o último publicado,
    marcado `estimated`; o Carimbo é o fim do último mês publicado. Com o IPCA do mês, sai exato."""
    month = date(2097, 2, 1)
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('IPCA', '2096-12-01', 0.4, 'bcb')"
            )
            estimated = await closing.real_since_start(conn, Decimal(12), month)
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('IPCA', '2097-01-01', 0.4, 'bcb')"
            )
            exact = await closing.real_since_start(conn, Decimal(12), month)
        finally:
            await tx.rollback()
    assert estimated.value is not None and estimated.estimated
    assert estimated.unavailable_reason is None
    assert estimated.as_of == date(2096, 12, 31)
    assert exact.value is not None and not exact.estimated
    assert exact.as_of == date(2097, 1, 31)
