"""Crescimento do patrimônio e melhor desempenho (Story 9.2 — FR-22, FR-34): no período da leitura,
crescimento = aporte + resultado — aporte = o aplicado que entrou no período (compras − vendas);
resultado = o resto, com os proventos —, as duas pontas da mesma fonte (snapshot ou ao vivo); a
rentabilidade por classe e por ativo das Posições e o ativo de melhor desempenho em destaque. Antes
do primeiro mês fechado, ou num fechado sem o consolidado B3 → indisponível com o motivo; "desde o
início" parte do zero."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel

from engines.common.dates import add_months, month_end, resolve_period, today_brt
from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id
from engines.portfolio.positions import GOALS_BLOCK
from engines.portfolio.valuation import valuation_as_of

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


@dataclass(frozen=True)
class _State:
    invested: Decimal  # valor investido (posições + cripto + caixa em corretora)
    applied: Decimal  # aplicado líquido até a data


async def _state(conn: asyncpg.Connection, month: date) -> tuple[_State | None, str | None]:
    """O investido e o aplicado no fim do mês, da mesma fonte nas duas pontas: o snapshot quando o
    mês está fechado, a valoração de hoje/fim do mês quando aberto. Antes do primeiro mês fechado ou
    num fechado sem o consolidado B3 → o motivo."""
    first = await conn.fetchval("SELECT min(month) FROM month_closes WHERE status = 'closed'")
    if first is None or month < first:
        return None, "antes_do_primeiro_fechamento"
    close = await service.latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        if dict(json.loads(close["coverage"])).get("B3") == NOT_COVERED:
            return None, "patrimonio_nao_coberto"
        t, _ = await service._frozen(conn, month, close["version"])
        if t["valor_investido"] is None or t["aplicado"] is None:
            return None, "patrimonio_nao_coberto"
        return _State(t["valor_investido"], t["aplicado"]), None
    owner = await get_owner_id(conn)
    v = await valuation_as_of(conn, owner, min(month_end(month), today_brt()))
    return _State(v.invested, v.contributed), None


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
    end, end_reason = await _state(conn, months[-1])
    if leitura == "inicio":  # desde o início: do zero (o aplicado inteiro é aporte)
        start: _State | None = _State(Decimal(0), Decimal(0))
        start_reason = None
    else:
        start, start_reason = await _state(conn, add_months(months[0], -1))
    reason = start_reason or end_reason
    available = start is not None and end is not None
    # aporte = o aplicado que entrou no período (compras − vendas); proventos ficam no resultado
    crescimento = end.invested - start.invested if start and end else None
    aporte = end.applied - start.applied if start and end else None
    end_value = end.invested if end else None
    start_value = start.invested if start else None
    return Growth(
        periodo=periodo,
        leitura=leitura,
        available=available,
        reason=reason,
        start_value=start_value if available else None,
        end_value=end_value if available else None,
        crescimento=crescimento,
        aporte=aporte,
        resultado=crescimento - aporte if crescimento is not None and aporte is not None else None,
        classes=class_returns,
        assets=sorted(ranked, key=lambda a: -(a.xirr_mensal or Decimal(0))),
        best=best,
    )
