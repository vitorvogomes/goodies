"""Avisos (AD-10 — Story 3.1): o contrato que toda engine usa para emitir aviso.

Cada engine expõe um provider `(conn, ctx) -> list[Alert]`, registrado em `main.py` na engine
`alerts`; nenhuma engine importa `alerts`. Avisos são calculados na leitura; só a dispensa é
gravada.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import asyncpg
from pydantic import BaseModel

from engines.common.month_status import MonthStatusPort

Severity = Literal["divergencia", "aviso"]


class AlertAction(BaseModel):
    label: str
    route: str
    params: dict[str, str] = {}


class Alert(BaseModel):
    key: str  # "<tipo>:<sujeito>" — estável enquanto o sujeito existir
    fingerprint: str  # hash da condição: dispensa vale até ele mudar
    severity: Severity
    message: str  # do catálogo do EXPERIENCE (Voice and Tone)
    action: AlertAction
    as_of: date | None = None
    dismissible: bool = True


@dataclass(frozen=True)
class AlertContext:
    today: date  # hoje em BRT
    periodo: date  # 1º dia do mês em foco
    months: MonthStatusPort
    owner_id: str
    # Cálculos caros compartilhados pelos providers numa leitura (ex.: a conferência da PF).
    memo: dict[str, Any] = field(default_factory=dict)


AlertProvider = Callable[[asyncpg.Connection, AlertContext], Awaitable[list[Alert]]]


def fingerprint(*parts: Any) -> str:
    """Hash curto e estável da condição do aviso: mudando um valor, a dispensa caduca."""
    raw = "\x1f".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def brl(value: Decimal | float) -> str:
    """ "R$ 1.234,56" (espaço sem quebra), como o front formata dinheiro."""
    q = Decimal(str(value)).quantize(Decimal("0.01"))
    sign = "−" if q < 0 else ""
    inteiro, centavos = f"{abs(q):.2f}".split(".")
    milhar = f"{int(inteiro):,}".replace(",", ".")
    return f"{sign}R$\u00a0{milhar},{centavos}"


AlertData = dict[str, float | int | str]


class LegacyAlert(BaseModel):
    """Formato intermediário do cálculo de gasto acima da média (`ledger.service`), que o provider
    converte em `Alert`."""

    type: str
    severity: str
    title: str
    message: str
    data: AlertData
