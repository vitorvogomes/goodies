"""Modelos de I/O do ledger (AD-2/AD-15) — rotas novas `/api/v1/ledger/*` (Story 2.7)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

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
    category_id: str


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
    account_id: str
    date: dt.date
    amount: Money
    description: str | None = None
    category_id: str


class ManualTransactionUpdate(BaseModel):
    account_id: str | None = None
    date: dt.date | None = None
    amount: Money | None = None
    description: str | None = None
    category_id: str | None = None
