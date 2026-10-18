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
