"""Orçamento do mês (Stories 6.5–6.7 — AD-15): tudo em `Money`/`Valued`, nada calculado no front."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from engines.common.models import Valued
from engines.common.money import Money, Pct


class PayerAmount(BaseModel):
    payer: str
    value: Money


class ResgateItem(BaseModel):
    date: date
    description: str
    value: Money


class ConsumedSub(BaseModel):
    name: str
    value: Money
    pct: Pct  # % do consumido
    count: int


class ConsumedGroup(BaseModel):
    group: str
    value: Money
    pct: Pct
    count: int
    subcategories: list[ConsumedSub]


class MonthBudget(BaseModel):
    month: date
    as_of: date | None
    source: str  # live | snapshot
    closed: bool
    trabalho: Valued[Decimal]
    trabalho_por_pagador: list[PayerAmount]
    resgates: Valued[Decimal]
    resgates_itens: list[ResgateItem]
    custos_fixos: Valued[Decimal]  # todos do mês: pago (valor pago) + a pagar (cadastrado)
    custos_fixos_pagos: Money
    custos_fixos_a_pagar: Money
    aporte_planejado: Money  # 0 quando não definido
    aporte_definido: bool
    dividas: Money
    dividas_informadas: bool  # False = pré-preenchido das transações em Dívidas
    dividas_prefill: Money
    disponivel: Valued[Decimal]
    consumido: Valued[Decimal]
    restante: Valued[Decimal]
    consumo_financiado: Valued[Decimal]
    restante_sem_resgates: Valued[Decimal]
    gastos: Money  # gastos brutos do mês
    deducao_fixos: Money  # custos fixos pagos (fora do consumido)
    deducao_dividas: Money
    devolucoes: Money
    investido: Money  # realizado total do mês, fora dos gastos
    taxa_poupanca: Valued[Decimal]  # em %; sem receita do trabalho → sem_receita
    aporte_sobre_trabalho: Valued[Decimal]  # investido ÷ trabalho, em %
    consumido_por_grupo: list[ConsumedGroup]
    grupos_total: Money  # Σ dos grupos (consumido antes das devoluções); base dos %
    # False: mês fechado antes do orçamento existir — só os totais congelados, sem o detalhe
    detalhe: bool = True


class DividasIn(BaseModel):
    valor: Money | None  # None = voltar ao pré-preenchido


class MonthPlanOut(BaseModel):
    month: date
    dividas: Money | None
    aporte_planejado: Money | None
