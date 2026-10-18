"""Protocolo `SourceAdapter` (AD-5 — Story 3.3): todo import passa por detect → parse → plan →
apply (e undo). Cada adapter vive na engine dona dos fatos que grava e se registra em `main.py`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

import asyncpg


@dataclass
class ParsedFile:
    source: str
    file_name: str
    file_hash: str  # sha256 do conteúdo: mesmo hash já aplicado = "arquivo já importado"
    content: bytes
    data: Any  # o que o adapter extraiu (lançamentos, operações...)


@dataclass
class FilePlan:
    """Plano de um arquivo: o que a prévia mostra e o que o `apply` grava."""

    source: str | None
    file_name: str
    file_hash: str
    account_id: str | None = None
    account_name: str | None = None
    broker: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    new: int = 0
    existing: int = 0
    skipped: int = 0
    reported_balance: Decimal | None = None
    reported_balance_date: date | None = None
    already_imported: bool = False
    needs: list[str] = field(default_factory=list)  # escolha pendente na linha ("account")
    warnings: list[str] = field(default_factory=list)  # avisos da linha (não mudam o apply)
    error: str | None = None
    overrides: dict[str, str] = field(default_factory=dict)
    # Entra no hash: o que mudaria o resultado do apply (ex.: os ids externos novos).
    fingerprint: dict[str, Any] = field(default_factory=dict)
    parsed: ParsedFile | None = None
    rows: list[Any] = field(default_factory=list)  # o que o apply grava

    def summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "account_id": self.account_id,
            "broker": self.broker,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "new": self.new,
            "existing": self.existing,
            "skipped": self.skipped,
            "reported_balance": self.reported_balance,
            "reported_balance_date": self.reported_balance_date,
            "needs": self.needs,
            "error": self.error,
            "overrides": self.overrides,
            "fingerprint": self.fingerprint,
        }


@dataclass
class Applied:
    inserted: int
    months: set[date] = field(default_factory=set)  # meses tocados (mark_dirty)
    detail: dict[str, Any] = field(default_factory=dict)


class PlanError(ValueError):
    """Arquivo reconhecido mas inválido (sem lançamentos, conta não cadastrada...)."""


class SourceAdapter(Protocol):
    sources: tuple[str, ...]

    def detect(self, file_name: str, content: bytes) -> str | None: ...

    def parse(self, source: str, file_name: str, content: bytes) -> Any: ...

    async def plan(
        self, conn: asyncpg.Connection, parsed: ParsedFile, overrides: dict[str, str]
    ) -> FilePlan: ...

    async def apply(self, conn: asyncpg.Connection, plan: FilePlan, batch_id: str) -> Applied: ...

    async def undo(self, conn: asyncpg.Connection, batch_id: str) -> None: ...
