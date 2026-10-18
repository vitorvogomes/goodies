"""Modelos de I/O da engine ingest (AD-2/AD-5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from engines.common.models import Uuid
from engines.common.money import Money

FileSource = Literal[
    "nubank_ofx", "nubank_csv", "b3_movimentacao", "b3_negociacao", "b3_consolidado"
]
RowSource = Literal[
    "nubank_ofx",
    "nubank_csv",
    "b3_movimentacao",
    "b3_negociacao",
    "b3_consolidado",
    "manual",
    "hermes",
    "derived",
]
BatchStatus = Literal["staged", "applied", "undone", "legacy"]


class BatchFileIn(BaseModel):
    """Um arquivo do lote: fonte, conta (Nubank) ou corretora (B3) e o período que ele cobre."""

    source: FileSource
    account_id: str | None = None
    broker: str | None = None
    file_name: str | None = None
    file_hash: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    reported_balance: Money | None = None
    reported_balance_date: date | None = None


class BatchFileResponse(BatchFileIn):
    id: str
    batch_id: str


class BatchResponse(BaseModel):
    id: str
    status: BatchStatus
    created_at: datetime
    applied_at: datetime | None
    files: list[BatchFileResponse]


# ---- Prévia → confirmação (Story 3.3) ----


class FilePlanOut(BaseModel):
    source: str | None
    file_name: str
    file_hash: str
    account_id: str | None
    account_name: str | None
    broker: str | None
    period_start: date | None
    period_end: date | None
    new: int
    existing: int
    skipped: int
    reported_balance: Money | None
    reported_balance_date: date | None
    already_imported: bool
    needs: list[str]
    warnings: list[str] = []
    error: str | None
    detail: dict[str, Any] = {}


class PreviewOut(BaseModel):
    batch_id: str
    hash: str
    expires_at: datetime
    files: list[FilePlanOut]
    new: int


class ReplanIn(BaseModel):
    batch_id: Uuid
    overrides: dict[str, dict[str, str]]  # por file_hash


class ConfirmIn(BaseModel):
    batch_id: Uuid
    hash: str


class ConfirmOut(BaseModel):
    batch_id: str
    imported: int
    files: list[FilePlanOut]
    applied: list[dict[str, Any]] = []  # detalhe de cada adapter, na ordem dos arquivos aplicados


class SourceRow(BaseModel):
    """Linha do Bloco Fontes (Story 3.9)."""

    key: str
    label: str
    kind: str
    updated_until: date | None
    stale: bool
    balance_status: Literal["conferido", "divergente"] | None = None  # só a conta PF
    balance_as_of: date | None = None
    balance_difference: Money | None = None


# ---- Histórico de imports e desfazer (Story 3.14) ----


class HistoryFile(BaseModel):
    source: str
    file_name: str | None
    period_start: date | None
    period_end: date | None


class HistoryBatch(BaseModel):
    id: str
    status: str
    created_at: datetime
    applied_at: datetime | None
    files: list[HistoryFile]
    new: int | None  # itens novos gravados (lote aplicado pelo Hub)
    undoable: bool


class ImportHistory(BaseModel):
    items: list[HistoryBatch]
    undo_note: str | None  # por que o último lote não tem Desfazer


class UndoPreview(BaseModel):
    batch_id: str
    applied_at: datetime
    transactions: int = 0
    operations: int = 0
    categorizations: int = 0
    rules: int = 0
    balances: int = 0
    snapshots: int = 0
    prices: int = 0  # preços do consolidado refeitos pelo consolidado anterior
    closed_months: list[str] = []  # "AAAA-MM" dos meses fechados que o desfazer ajusta (5.6)
