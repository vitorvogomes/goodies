"""Núcleo puro do ledger (AD-2: Decimal, sem IO).

Story 2.5 — escolha da regra de categoria (AD-6): "descrição contém", com direção pelo sinal
(entrada > 0, saída < 0, ambos); vence a condição mais longa; empate → a regra mais recente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Rule:
    pattern: str
    direction: str  # entrada | saida | ambos
    category_id: str
    category_name: str
    kind: str  # kind do grupo da subcategoria
    rule_id: str | None = None
    created_at: datetime | None = None


def direction_of(amount: Decimal) -> str:
    return "entrada" if amount > 0 else "saida"


def best_rule(description: str, amount: Decimal, rules: Sequence[Rule]) -> Rule | None:
    text = (description or "").lower()
    side = direction_of(amount)
    candidates = [
        r
        for r in rules
        if r.pattern and r.pattern.lower() in text and r.direction in (side, "ambos")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (len(r.pattern), r.created_at or _EPOCH, r.rule_id or ""))
