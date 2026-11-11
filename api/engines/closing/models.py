"""Resumo do mês (AD-8 — Story 5.2): os termos da AD-7 de um mês, ao vivo (e, a partir da 5.3,
congelados no fechamento)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.common.shares import Slice
from engines.planning.models import MonthBudget
from engines.portfolio.positions import PositionClass


class MonthSummary(BaseModel):
    month: date
    as_of: date  # fim do mês, ou hoje no mês corrente
    source: str = "live"
    # caixa (ledger/calc)
    receitas: Money
    trabalho: Money
    resgates: Money
    devolucoes: Money
    gastos: Money
    investido: Money
    taxa_poupanca: Pct | None  # em %
    resultado_mes: Money
    # orçamento (planning/calc — Story 6.5)
    consumido: Money
    disponivel: Money
    restante: Money
    restante_sem_resgates: Money
    consumo_financiado: Money
    receitas_por_pagador: dict[str, Money]
    gastos_por_categoria: dict[str, Money]
    ledger_as_of: date | None
    income_as_of: date | None  # trabalho/poupança: o MEI pode não cobrir o mês
    income_stale: bool
    saldo_conferido_pf: bool | None
    # investimentos (portfolio/calc)
    saldo_contas: Money
    valor_investido: Money
    patrimonio: Money
    aplicado: Money
    resultado_investimentos: Money
    rentabilidade: Pct | None  # XIRR desde o início até as_of, em % a.a.
    # Story 7.3: XIRR do mês (fim do mês anterior → fim do mês), % a.a.; real descontado o IPCA
    rentabilidade_mes: Pct | None = None
    rentabilidade_mes_real: Pct | None = None
    valor_por_classe: dict[str, Money]
    valor_por_ativo: dict[str, Money]
    caixa_corretora: Money
    a_caminho: Money = Decimal(0)  # Story 7.7: transferido, fora do patrimônio até o relatório
    # Story 8.7: o andamento do aporte do mês (planning)
    aporte_planejado: Money | None = None  # None = não definido
    realizado: Money = Decimal(0)  # o investimento do mês, com o a caminho
    pendente: Money = Decimal(0)  # planejado − realizado (sem planejado: `nao_definido`)
    realizado_por_classe: dict[str, Money] = Field(default_factory=dict)
    realizado_por_ativo: dict[str, Money] = Field(default_factory=dict)  # por assets.id
    # Para o snapshot (AD-8): valor por `assets.id` e fluxos líquidos por (classe, data) no mês.
    asset_ids_value: dict[str, Money] = Field(default_factory=dict, exclude=True)
    flows: dict[tuple[str, date], Money] = Field(default_factory=dict, exclude=True)
    portfolio_as_of: date | None
    portfolio_stale: bool
    coverage: dict[str, str]  # fonte → método de valoração ("B3: consolidado de 30/09/2026")
    # Conta do orçamento inteira (Story 6.5): congelada junto no fechamento.
    budget: MonthBudget | None = Field(default=None, exclude=True)
    # Termo sem valor no snapshot → motivo (`fora_do_resumo`: não existia quando o mês fechou).
    unavailable: dict[str, str] = Field(default_factory=dict)


class CloseCheck(BaseModel):
    """Precondição do fechamento (AD-8): `bloqueia` impede; `confirma` pede "fechar mesmo assim"."""

    code: str
    kind: str  # bloqueia | confirma
    message: str
    amount: Money | None = None  # diferença do saldo PF divergente
    reason: str | None = None  # "retroativo" na confirmação automática do fechamento retroativo


class CloseIn(BaseModel):
    confirmar: list[str] = []  # códigos das verificações `confirma` aceitas


class CloseOut(BaseModel):
    month: date
    version: int
    confirmations: list[CloseCheck]


class MonthState(BaseModel):
    month: date
    status: str  # aberto | fechado | ajuste
    version: int | None
    closed_at: datetime | None
    origin: str | None


class ChecklistItem(BaseModel):
    key: str
    code: str | None = None  # código da verificação (o que vai em `confirmar`)
    ok: bool
    kind: str  # bloqueia | confirma | info
    message: str


class Checklist(BaseModel):
    month: date
    items: list[ChecklistItem]
    blocking: int  # pendências que impedem o fechamento
    pending: int  # pendências que pedem "fechar mesmo assim"
    summary: MonthSummary  # o que vai ser congelado


class ReopenRow(BaseModel):
    metric: str
    label: str
    frozen: Money | None
    live: Money | None


class ReopenPreview(BaseModel):
    """Congelado × recalculado (Story 5.5): só as métricas que mudam, arredondadas a 2 casas."""

    month: date
    version: int
    rows: list[ReopenRow]


class ReopenOut(BaseModel):
    month: date
    version: int
    status: str


class RecoveryStep(BaseModel):
    key: str  # importar | revisar | conferir | fechar
    label: str
    state: str  # feito | atual | a_fazer
    detail: str | None = None
    href: str | None = None


class RecoveryMonth(BaseModel):
    month: date
    status: str  # aberto | fechado | ajuste


class Recovery(BaseModel):
    """Assistente de recuperação (Story 5.8 — UX-DR41): tudo derivado dos dados."""

    active: bool
    base_until: date | None
    message: str | None
    months: list[RecoveryMonth]
    current: date | None
    steps: list[RecoveryStep]


class MonthSource(BaseModel):
    month: date
    source: str  # snapshot (fechado) | live


class PeriodSummary(BaseModel):
    """Soma dos meses do período (Story 7.1): termos de fluxo de cada mês, do snapshot quando
    fechado e ao vivo quando aberto; nunca inclui mês depois do período."""

    months: list[MonthSource]
    receitas: Money
    trabalho: Money
    resgates: Money
    devolucoes: Money
    gastos: Money
    investido: Money
    resultado_mes: Money
    consumido: Money
    # Story 9.1: o mais antigo dos meses, o OU dos defasados e a taxa dos componentes somados
    as_of: date | None = None
    stale: bool = False
    taxa_poupanca: Pct | None = None


class OnTheWay(BaseModel):
    broker: str
    value: Money
    import_from: date | None  # "importe o relatório B3 a partir de dd/mm/aaaa"


class PositionsReport(BaseModel):
    periodo: str
    leitura: str
    as_of: date
    months: list[MonthSource]
    classes: list[PositionClass]
    aplicado: Money
    valor: Money
    caixa_corretora: Money = Decimal(0)  # Story 7.7: no patrimônio
    total: Money = Decimal(0)  # valor das posições + caixa em corretora (sem o a caminho)
    a_caminho: list[OnTheWay] = Field(default_factory=list)  # fora do patrimônio
    xirr_nominal: Valued[Decimal]  # consolidado do período, % a.a.
    xirr_real: Valued[Decimal]  # descontado o IPCA do período; sem o IPCA do último mês: aguardando
    ipca_ate: date | None  # último mês com IPCA publicado
    resultado_total: Money = Decimal(0)  # desde o primeiro aporte
    xirr_mensal: Pct | None = None  # o XIRR nominal consolidado ao mês
    # v2.2 (pizza da carteira): % de cada classe (e do caixa na corretora) e de cada ativo no total
    distribuicao: list[Slice] = Field(default_factory=list)
    distribuicao_ativos: list[Slice] = Field(default_factory=list)
