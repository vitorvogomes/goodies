"""Orçamento do mês (Stories 6.5–6.7 — AD-15): tudo em `Money`/`Valued`, nada calculado no front."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.ledger.expected_incomes import PlannedIncome


def _out_of_summary() -> Valued[Decimal]:
    return Valued[Decimal](unavailable_reason="fora_do_resumo")


class PayerAmount(BaseModel):
    payer: str
    value: Money


class ResgateItem(BaseModel):
    date: date
    description: str
    value: Money
    goal: str | None = None  # Story 8.1: o objetivo do ativo resgatado (None = carteira)


class ConsumedSub(BaseModel):
    name: str
    value: Money
    pct: Pct  # % do consumido
    count: int


class ConsumedGroup(BaseModel):
    group: str
    value: Money  # consumido (variável)
    pct: Pct
    count: int
    subcategories: list[ConsumedSub]
    # o que o grupo pagou em custo fixo e em dívida (fora do consumido)
    fixos: Money = Decimal(0)
    dividas: Money = Decimal(0)


class FlowPartOut(BaseModel):
    key: str  # custos_fixos | aporte | dividas | gastos | sobra
    label: str
    value: Money
    pct: Pct  # % da barra (as fatias somam 100)


class MonthFlowOut(BaseModel):
    """Fluxo do mês do Painel (v2.2): para onde foram as entradas; `sobra` = o restante."""

    entradas: Money
    sobra: Money
    parts: list[FlowPartOut]
    limite_pct: Pct | None  # onde as entradas acabam na barra (< 100 = as saídas passaram)


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
    # Story 8.1: o financiado dividido — por objetivo (tom neutro) e por resgate da carteira
    # (laranja); snapshot de antes da 8.1 → fora do resumo
    financiado_objetivo: Valued[Decimal] = Field(default_factory=_out_of_summary)
    financiado_carteira: Valued[Decimal] = Field(default_factory=_out_of_summary)
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
    # fora dos termos do golden: o investimento do mês por categoria (não é
    # custo), o aporte planejado − realizado e as receitas esperadas × recebidas; o a receber entra
    # num disponível à parte
    investido_por_categoria: list[ConsumedSub] = Field(default_factory=list)
    aporte_diferenca: Money | None = None  # planejado − realizado; None = aporte não definido
    receitas_planejadas: list[PlannedIncome] = Field(default_factory=list)
    receita_planejada: Money = Decimal(0)
    receita_a_receber: Money = Decimal(0)
    disponivel_com_a_receber: Valued[Decimal] = Field(default_factory=_out_of_summary)
    fluxo: MonthFlowOut | None = None  # v2.2; resumo congelado antes dele: sem barra


class OportunidadeIn(BaseModel):
    ativo: bool


class DividasIn(BaseModel):
    valor: Money | None  # None = voltar ao pré-preenchido


class AporteIn(BaseModel):
    valor: Money | None = Field(default=None, ge=0)  # None = não definido


class MonthPlanOut(BaseModel):
    month: date
    dividas: Money | None
    aporte_planejado: Money | None
    oportunidade: bool = False  # v2.2: a divisão entre os ativos pesa a variação do preço
