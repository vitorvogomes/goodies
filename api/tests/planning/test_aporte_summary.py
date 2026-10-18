"""Story 8.8 — Resumo do aporte no Painel (planejado, realizado com o a caminho, barra, a caminho
por corretora, classes fora da banda, % realizado) e o aviso "Faltam R$ {valor} do aporte de {mês}."
nos últimos 7 dias do mês com pendente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.common.alerts import AlertContext
from engines.planning import progress as progress_service
from engines.planning import summary as summary_service

D = Decimal


@pytest.mark.asyncio
async def test_summary_route(api, auth_headers) -> None:
    import main  # noqa: F401

    r = await api.get("/api/v1/planning/months/2093-07/aporte/resumo", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aporte_definido"] is False and body["closed"] is False
    assert set(body) >= {"andamento", "fora_da_banda", "a_caminho", "as_of"}


def _fixed(planned: Decimal | None, realizado: Decimal) -> Any:
    async def month_progress(conn: Any, month: date) -> progress_service.MonthProgress:
        return progress_service.MonthProgress(planned, realizado, {}, {}, {})

    return month_progress


@pytest.mark.asyncio
async def test_pending_alert_in_the_last_7_days(pool, monkeypatch) -> None:
    def ctx(day: date) -> AlertContext:
        return AlertContext(today=day, periodo=day.replace(day=1), months=None, owner_id="x")  # type: ignore[arg-type]

    async with pool.acquire() as conn:
        monkeypatch.setattr(summary_service.progress, "month_progress", _fixed(D(4500), D(2800)))
        late = await summary_service.aporte_alerts(conn, ctx(date(2097, 10, 25)))
        early = await summary_service.aporte_alerts(conn, ctx(date(2097, 10, 24)))
        monkeypatch.setattr(summary_service.progress, "month_progress", _fixed(D(4500), D(4600)))
        done = await summary_service.aporte_alerts(conn, ctx(date(2097, 10, 31)))
        monkeypatch.setattr(summary_service.progress, "month_progress", _fixed(None, D(0)))
        undefined = await summary_service.aporte_alerts(conn, ctx(date(2097, 10, 31)))
    assert [a.message for a in late] == ["Faltam R$\u00a01.700,00 do aporte de out/2097."]
    assert late[0].action is not None and late[0].action.label == "Ver aportes"
    assert early == [] and done == [] and undefined == []
