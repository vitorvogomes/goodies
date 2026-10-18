"""Story 5.3 — fechar o mês: precondições por registro (bloqueia × confirma, "fechar mesmo assim"
gravado), versão 1 com o resumo congelado (snapshot = ao vivo no instante do fechamento) e o status
do mês pelo MonthStatusPort."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.closing import service as closing
from engines.common.month_status import month_status

URL = "/api/v1/closing/months"
MONTH = date(2025, 4, 1)


@pytest.fixture
async def no_closes(pool: Any):
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM month_closes WHERE month = $1", MONTH)


@pytest.mark.asyncio
async def test_close_flow(api, auth_headers, pool, no_closes) -> None:
    import main  # noqa: F401

    checks = (await api.get(f"{URL}/2025-04/checks", headers=auth_headers)).json()
    assert all(set(c) >= {"code", "kind", "message"} for c in checks)
    blocking = [c for c in checks if c["kind"] == "bloqueia"]
    confirm = [c["code"] for c in checks if c["kind"] == "confirma"]
    async with pool.acquire() as conn:
        pending = await conn.fetchval(
            "SELECT count(*) FROM transactions WHERE review_status = 'pending' "
            "AND date >= '2025-04-01' AND date < '2025-05-01'"
        )
    assert bool(blocking) == bool(pending) or blocking  # pendentes bloqueiam
    if blocking:
        r = await api.post(
            f"{URL}/2025-04/close", json={"confirmar": confirm}, headers=auth_headers
        )
        assert r.status_code == 409 and r.json()["detail"]["error"] == "fechamento_bloqueado"
        return
    if confirm:
        r = await api.post(f"{URL}/2025-04/close", json={"confirmar": []}, headers=auth_headers)
        assert r.status_code == 409 and r.json()["detail"]["error"] == "confirmacao_pendente"
    async with pool.acquire() as conn:
        live = await closing.build_month_summary(conn, MONTH)
    r = await api.post(f"{URL}/2025-04/close", json={"confirmar": confirm}, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 1
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM month_summary_totals WHERE month = $1 AND version = 1", MONTH
        )
        close = await conn.fetchrow("SELECT * FROM month_closes WHERE month = $1", MONTH)
        lines = await conn.fetchval(
            "SELECT count(*) FROM month_summary_lines WHERE month = $1 AND version = 1", MONTH
        )
        assert await month_status().status(conn, MONTH) == "fechado"
    # golden: snapshot = ao vivo no instante do fechamento
    for term in (
        "receitas",
        "gastos",
        "investido",
        "resultado_mes",
        "patrimonio",
        "valor_investido",
        "rentabilidade_mes",
        "rentabilidade_mes_real",
        "caixa_corretora",
        "a_caminho",
        "realizado",  # Story 8.7: o andamento do aporte no golden snapshot = ao vivo
    ):
        assert row[term] == getattr(live, term), term
    # sem aporte planejado, o pendente congela nulo com o motivo
    expected_pending = live.pendente if live.aporte_planejado is not None else None
    assert row["pendente"] == expected_pending
    async with pool.acquire() as conn:
        frozen = await closing.month_summary(conn, MONTH)
    assert frozen.source == "snapshot"
    assert frozen.realizado_por_classe == live.realizado_por_classe
    assert frozen.realizado_por_ativo == live.realizado_por_ativo
    assert frozen.aporte_planejado == live.aporte_planejado
    assert row["unavailable"]  # termos de engines futuras: fora_do_resumo
    assert close["origin"] == "live" and close["status"] == "closed"
    assert close["coverage"]
    expected = (
        len(live.receitas_por_pagador)
        + len(live.gastos_por_categoria)
        + len(live.valor_por_classe)
        + len(live.asset_ids_value)
        + len(live.flows)
        + len(live.realizado_por_classe)
        + len(live.realizado_por_ativo)
    )
    assert lines == expected
    again = await api.post(
        f"{URL}/2025-04/close", json={"confirmar": confirm}, headers=auth_headers
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_current_month_cannot_close(api, auth_headers) -> None:
    import main  # noqa: F401
    from engines.common.dates import today_brt

    periodo = f"{today_brt():%Y-%m}"
    checks = (await api.get(f"{URL}/{periodo}/checks", headers=auth_headers)).json()
    assert any(c["code"] == "mes_em_curso" and c["kind"] == "bloqueia" for c in checks)


@pytest.mark.asyncio
async def test_extreme_savings_rate_fits(pool) -> None:
    """Revisão do Épico 5: trabalho de R$ 5 e gastos de R$ 6.000 dão −119.900 % — o snapshot
    precisa guardar (antes estourava numeric(9,4) e o fechamento caía)."""
    from decimal import Decimal

    month = date(2003, 3, 1)
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO month_closes (month, version, status) VALUES ($1, 1, 'closed')",
                    month,
                )
                await conn.execute(
                    "INSERT INTO month_summary_totals (month, version, as_of, taxa_poupanca) "
                    "VALUES ($1, 1, '2003-03-31', $2)",
                    month,
                    Decimal("-119900.00"),
                )
                value = await conn.fetchval(
                    "SELECT taxa_poupanca FROM month_summary_totals WHERE month = $1", month
                )
                assert value == Decimal("-119900.00")
                raise _Rollback
        except _Rollback:
            pass


class _Rollback(Exception):
    pass
