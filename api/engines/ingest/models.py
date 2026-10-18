"""Modelos de I/O da engine ingest (AD-2/AD-5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

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
