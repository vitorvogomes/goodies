"""Modelos de I/O do ledger (AD-2/AD-15) — rotas novas `/api/v1/ledger/*` (Story 2.7)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from engines.common.models import Uuid
from engines.common.money import Money

KIND_LABEL = {
    "income": "Receita",
    "expense": "Despesa",
    "investment": "Investimento",
    "transfer": "Transferência",
}


class TransactionRow(BaseModel):
    id: str
    date: dt.date
    description: str | None
    amount: Money
    kind: str
    kind_label: str
    category_id: str
    category_name: str
    category_key: str
    group_name: str
    category_source: str
    review_status: str
    payer: str | None
    account_id: str
    account_name: str
    source: str
    batch_id: str | None
    file_name: str | None
    rule_pattern: str | None


class TransactionList(BaseModel):
    items: list[TransactionRow]
    total: int
    limit: int
    offset: int


class CategoryChangeIn(BaseModel):
    category_id: Uuid


class CategoryOption(BaseModel):
    id: str
    key: str
    name: str
    label: str  # "Grupo › Subcategoria"
    group_key: str
    group_name: str
    kind: str
    role: str
    is_active: bool


class ManualTransactionCreate(BaseModel):
    account_id: Uuid
    date: dt.date
    amount: Money
    description: str | None = None
    category_id: Uuid


class ManualTransactionUpdate(BaseModel):
    account_id: Uuid | None = None
    date: dt.date | None = None
    amount: Money | None = None
    description: str | None = None
    category_id: Uuid | None = None


GROUP_KIND_LABEL = {
    "income": "Receita",
    "expense": "Gasto",
    "investment": "Investimento",
    "transfer": "Transferência",
}
ROLE_LABEL = {
    "work_income": "Receita do trabalho",
    "resgate": "Resgate",
    "devolucao": "Devolução",
    "divida": "Dívida",
    "consumo": "Consumo",
    "investimento": "Investimento",
    "transferencia": "Transferência",
    "a_classificar": "A classificar",
}
DEFAULT_ROLE = {
    "income": "work_income",
    "expense": "consumo",
    "investment": "investimento",
    "transfer": "transferencia",
}
ROLES_BY_KIND = {
    "income": ("work_income", "resgate", "devolucao"),
    "expense": ("consumo", "divida"),
    "investment": ("investimento",),
    "transfer": ("transferencia",),
}
Kind = Literal["income", "expense", "investment", "transfer"]
Role = Literal[
    "work_income", "resgate", "devolucao", "divida", "consumo", "investimento", "transferencia"
]


class CategoryNode(BaseModel):
    id: str
    key: str
    name: str
    group_id: str
    kind: str
    role: str
    role_label: str
    is_active: bool
    is_system: bool
    transaction_count: int


class CategoryGroupNode(BaseModel):
    id: str
    key: str
    name: str
    kind: str
    kind_label: str
    is_active: bool
    is_system: bool
    transaction_count: int
    categories: list[CategoryNode]


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Kind


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    kind: Kind | None = None
    is_active: bool | None = None


class SubcategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    group_id: Uuid
    role: Role | None = None


class SubcategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    group_id: Uuid | None = None
    role: Role | None = None
    is_active: bool | None = None


Direction = Literal["entrada", "saida", "ambos"]


class RuleRow(BaseModel):
    id: str
    pattern: str
    direction: str
    category_id: str
    category_label: str
    is_active: bool
    origin: str
    created_at: dt.datetime


class RuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, max_length=120)
    direction: Direction | None = None
    category_id: Uuid | None = None
    is_active: bool | None = None


class RulePreviewIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=120)
    direction: Direction


class RuleMatch(BaseModel):
    id: str
    date: dt.date
    description: str | None
    amount: Money
    category_label: str


class RulePreviewOut(BaseModel):
    total: int
    items: list[RuleMatch]


class ReapplyIn(BaseModel):
    de: str = Field(pattern=r"^\d{4}-\d{2}$")
    ate: str = Field(pattern=r"^\d{4}-\d{2}$")


class ReapplyChange(BaseModel):
    transaction_id: str
    date: dt.date
    description: str | None
    amount: Money
    before: str
    after: str
    rule_pattern: str


class ReapplyPreview(BaseModel):
    changes: list[ReapplyChange]
    manual_unchanged: int
    closed_months: int


class ReapplyResult(BaseModel):
    changed: int


# ---- Revisão de transações (Story 3.10) ----
Origin = Literal["regra", "sugestao", "sem_sugestao", "manual"]


class ReviewDebenture(BaseModel):
    """Aporte em debênture sugerido (Story 7.6): vem do registro do portfolio."""

    contribution_id: str
    label: str  # "Flash · Pré 24% a.a."
    amount: Money


class ReviewItem(BaseModel):
    id: str
    date: dt.date
    month: str
    description: str | None
    amount: Money
    account_name: str
    category_id: str
    category_label: str
    category_kind: str
    origin: Origin
    rule_pattern: str | None
    debenture: ReviewDebenture | None = None


class ReviewMonth(BaseModel):
    month: str
    count: int
    entradas: Money
    saidas: Money


class ReviewList(BaseModel):
    items: list[ReviewItem]
    months: list[ReviewMonth]
    total: int


class ReviewChoice(BaseModel):
    transaction_id: Uuid
    category_id: Uuid


class ReviewConfirmIn(BaseModel):
    items: list[ReviewChoice] = Field(min_length=1)
    lote: Uuid | None = None


class ReviewConfirmOut(BaseModel):
    confirmed: int
    remaining: int


# ---- Proposta de regra (Story 3.11) ----


class RuleProposalIn(BaseModel):
    transaction_id: Uuid
    category_id: Uuid


class RuleProposal(BaseModel):
    pattern: str
    direction: Direction
    category_id: str
    category_label: str
    affected: int  # outras transações não manuais que a regra mudaria


class RuleCreate(BaseModel):
    pattern: str = Field(min_length=1, max_length=120)
    direction: Direction
    category_id: Uuid
    lote: Uuid | None = None  # vinda da Revisão: created_in_batch


class RuleCreated(BaseModel):
    rule: RuleRow
    applied: int


# ---- Conferência de saldo na tela (Story 3.13) ----


class BalanceCandidate(BaseModel):
    id: str
    date: dt.date
    description: str | None
    amount: Money
    category_label: str


class BalanceCandidates(BaseModel):
    start: dt.date
    end: dt.date
    difference: Money
    items: list[BalanceCandidate]


# ---- Custos fixos v2 (Story 6.1 — FR-18) ----


class FixedCostIn(BaseModel):
    name: str = Field(min_length=1)
    amount: Money
    due_day: int  # 1–31, validado na rota com a mensagem do catálogo
    category_id: Uuid
    valid_from: dt.date | None = None  # 1º dia do mês; sem → mês atual


class FixedCostPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    amount: Money | None = None
    due_day: int | None = None
    category_id: Uuid | None = None


class FixedCostRow(BaseModel):
    id: str
    name: str
    amount: Money
    due_day: int
    category_id: str | None  # custo antigo sem categoria da v2
    category_label: str
    valid_from: dt.date
    valid_to: dt.date | None


# ---- Custos fixos do mês com casamento (Story 6.2) ----


class FixedCostTx(BaseModel):
    id: str
    date: dt.date
    description: str | None
    amount: Money  # com sinal (saída negativa)


class FixedCostMonthItem(BaseModel):
    id: str
    name: str
    amount: Money  # valor cadastrado
    due_date: dt.date
    category_label: str
    status: Literal["pago", "manual", "pendente", "vencendo", "atrasado"]
    source: str | None  # decisao | auto
    transaction: FixedCostTx | None
    candidates: list[FixedCostTx]  # "2 candidatas": nada pago até escolher


class FixedCostMonth(BaseModel):
    month: dt.date
    closed: bool  # mês fechado: só leitura até reabrir
    items: list[FixedCostMonthItem]
    count: int
    paid_count: int
    total: Money  # Σ valores cadastrados
    paid_total: Money  # Σ pago (transação casada; manual = valor cadastrado)
    pending_total: Money  # Σ cadastrado do que falta pagar
    as_of: dt.date | None = None  # dados até: último lançamento até o fim do mês


class FixedCostDecisionIn(BaseModel):
    mes: str = Field(pattern=r"^\d{4}-\d{2}$")
    kind: Literal["confirmado", "corrigido", "manual", "desfeito"]
    transaction_id: Uuid | None = None
