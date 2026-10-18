"""Crescimento do patrimônio e melhor desempenho (Story 9.2 — FR-22, FR-34): no período da leitura,
crescimento = aporte + resultado (aporte = dinheiro que entrou líquido nas posições; resultado = o
resto, com os proventos), a rentabilidade por classe e por ativo das Posições e o ativo de melhor
desempenho em destaque. Sem o início coberto (antes do primeiro mês fechado, ou um retroativo sem o
consolidado B3) → indisponível com o motivo; "desde o início" parte do zero."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel

from engines.common.dates import add_months, resolve_period
from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.portfolio.positions import GOALS_BLOCK

from . import service

_CENT = Decimal("0.01")
NOT_COVERED = "patrimônio não coberto"


class ClassReturn(BaseModel):
    key: str
    label: str
    xirr_nominal: Valued[Decimal]
    resultado: Money | None


class AssetReturn(BaseModel):
    symbol: str
    cls: str
    xirr_mensal: Pct | None  # % a.m. do período
    resultado: Money | None


class Growth(BaseModel):
    periodo: str
    leitura: str
    available: bool
    reason: str | None  # antes_do_primeiro_fechamento | patrimonio_nao_coberto
    start_value: Money | None
    end_value: Money | None
    crescimento: Money | None
    aporte: Money | None
    resultado: Money | None
    classes: list[ClassReturn]
    assets: list[AssetReturn]
    best: AssetReturn | None  # o ativo de melhor desempenho (maior % a.m. no período)


async def _start(conn: asyncpg.Connection, month: date) -> tuple[Decimal | None, str | None]:
    """Valor investido no fim do mês anterior ao período, ou o motivo de não ter."""
    found = await service._class_values_at(conn, month)
    if found is None:
        return None, "antes_do_primeiro_fechamento"
    close = await service.latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        if dict(json.loads(close["coverage"])).get("B3") == NOT_COVERED:
            return None, "patrimonio_nao_coberto"
    values, _ = found
    return sum(values.values(), Decimal(0)), None


async def growth(conn: asyncpg.Connection, periodo: str, leitura: str) -> Growth:
    months = resolve_period(periodo, leitura)
    report = await service.positions(conn, periodo, leitura)
    classes = [c for c in report.classes if c.key != GOALS_BLOCK]
    assets = [
        AssetReturn(symbol=a.symbol, cls=c.key, xirr_mensal=a.xirr_mensal, resultado=a.resultado)
        for c in report.classes
        for a in c.assets
    ]
    ranked = [a for a in assets if a.xirr_mensal is not None]
    best = max(ranked, key=lambda a: a.xirr_mensal or Decimal(0)) if ranked else None
    class_returns = [
        ClassReturn(key=c.key, label=c.label, xirr_nominal=c.xirr_nominal, resultado=c.resultado)
        for c in classes
    ]
    end_value = sum((c.valor for c in report.classes), Decimal(0))
    if leitura == "inicio":  # desde o início: do zero, o aplicado é o aporte
        start_value: Decimal | None = Decimal(0)
        reason = None
        aporte: Decimal | None = report.aplicado
    else:
        start_value, reason = await _start(conn, add_months(months[0], -1))
        flows = Decimal(0)
        for m in months:
            s = await service.month_summary(conn, m)
            flows += sum(s.flows.values(), Decimal(0))
        aporte = -flows  # no sinal do XIRR o aporte é negativo; proventos entram no resultado
    available = start_value is not None
    crescimento = end_value - start_value if start_value is not None else None
    return Growth(
        periodo=periodo,
        leitura=leitura,
        available=available,
        reason=reason,
        start_value=start_value,
        end_value=end_value if available else None,
        crescimento=crescimento,
        aporte=aporte if available else None,
        resultado=crescimento - aporte if crescimento is not None and aporte is not None else None,
        classes=class_returns,
        assets=sorted(ranked, key=lambda a: -(a.xirr_mensal or Decimal(0))),
        best=best,
    )
