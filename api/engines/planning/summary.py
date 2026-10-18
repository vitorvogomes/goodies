"""Resumo do aporte no Painel e aviso de pendente (Story 8.8 — FR-13, FR-14, FR-31): o planejado,
o realizado (com o a caminho), a Barra de progresso, o a caminho por corretora ("importe o relatório
B3 a partir de dd/mm/aaaa"), quantas classes estão fora da banda e o % realizado — tudo da API
(AD-4). Nos últimos 7 dias do mês com pendente: "Faltam R$ {valor} do aporte de {mês}."."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel

from engines.common.alerts import Alert, AlertAction, AlertContext, brl, fingerprint
from engines.common.dates import month_end, month_label, today_brt
from engines.common.money import Money
from engines.common.month_status import month_status
from engines.common.owner import get_owner_id
from engines.portfolio import brokers as portfolio_brokers

from . import distribution_service, progress

LAST_DAYS = 7  # "os últimos 7 dias do mês"


class OnTheWay(BaseModel):
    broker: str
    value: Money
    import_from: date | None


class AporteSummary(BaseModel):
    month: date
    as_of: date
    aporte_definido: bool
    closed: bool  # mês fechado: sem campo para definir o aporte (só leitura)
    andamento: distribution_service.Andamento
    fora_da_banda: int  # classes fora da banda → "Ver aportes"
    a_caminho: list[OnTheWay]  # o dinheiro a caminho das corretoras (Story 7.7)


async def aporte_summary(conn: asyncpg.Connection, month: date) -> AporteSummary:
    preview = await distribution_service.preview(conn, month)
    as_of = min(month_end(month), today_brt())
    owner = await get_owner_id(conn)
    brokers = await portfolio_brokers.broker_cash_as_of(conn, owner, as_of)
    return AporteSummary(
        month=month,
        as_of=as_of,
        aporte_definido=preview.aporte_definido,
        closed=await month_status().is_closed(conn, month),
        andamento=preview.andamento,
        fora_da_banda=sum(1 for c in preview.classes if c.out_of_band),
        a_caminho=[
            OnTheWay(broker=b.name, value=b.a_caminho, import_from=b.import_from)
            for b in brokers
            if b.a_caminho > 0
        ],
    )


async def aporte_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """ "Faltam R$ {valor} do aporte de {mês}." (Ver aportes) nos últimos 7 dias do mês."""
    month = ctx.today.replace(day=1)
    if (month_end(month) - ctx.today).days >= LAST_DAYS:
        return []
    p = await progress.month_progress(conn, month)
    if p.planned is None:
        return []
    missing = p.planned - p.realizado
    if missing <= 0:
        return []
    return [
        Alert(
            key=f"aporte_pendente:{month:%Y-%m}",
            fingerprint=fingerprint(missing.quantize(Decimal("0.01")), month),
            severity="aviso",
            message=f"Faltam {brl(missing)} do aporte de {month_label(month)}.",
            action=AlertAction(
                label="Ver aportes",
                route="/investimentos/aportes",
                params={"periodo": f"{month:%Y-%m}"},
            ),
            as_of=ctx.today,
        )
    ]
