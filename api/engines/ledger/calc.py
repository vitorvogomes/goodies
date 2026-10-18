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
    # Mais longa; empate → a mais recente; empate total → o menor id (ORDER BY da revisão 0019).
    top = max((len(r.pattern), r.created_at or _EPOCH) for r in candidates)
    tied = [r for r in candidates if (len(r.pattern), r.created_at or _EPOCH) == top]
    return min(tied, key=lambda r: r.rule_id or "")


# --------------------------------------------------------------------------------------------
# Termos de dinheiro do mês (AD-7 — Story 2.6): uma função pura por termo, lida por `role`.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Movement:
    """Uma transação vista pelos termos: valor com sinal, `kind` (cópia do grupo) e `role`."""

    amount: Decimal
    kind: str
    role: str


def _sum(movements: Sequence[Movement], role: str) -> Decimal:
    return sum((m.amount for m in movements if m.role == role), Decimal(0))


def work_income(movements: Sequence[Movement]) -> Decimal:
    """Receita do trabalho (role `work_income`): nunca resgate, devolução nem a classificar."""
    return _sum(movements, "work_income")


def resgates(movements: Sequence[Movement]) -> Decimal:
    return _sum(movements, "resgate")


def devolucoes(movements: Sequence[Movement]) -> Decimal:
    return _sum(movements, "devolucao")


def gastos(movements: Sequence[Movement]) -> Decimal:
    """Gastos brutos (magnitude): Σ das transações de `kind = expense` (estorno abate)."""
    return -sum((m.amount for m in movements if m.kind == "expense"), Decimal(0))


def investido(movements: Sequence[Movement]) -> Decimal:
    """Investimento líquido do mês (magnitude das aplicações; resgate é receita desde o ADR-015)."""
    return -sum((m.amount for m in movements if m.kind == "investment"), Decimal(0))


def receitas(movements: Sequence[Movement]) -> Decimal:
    return sum((m.amount for m in movements if m.kind == "income"), Decimal(0))


def savings_rate(movements: Sequence[Movement]) -> Decimal | None:
    """Taxa de poupança (fração): (trabalho - (gastos - devoluções)) / trabalho. Sem receita do
    trabalho → None (`sem_receita`), nunca 0%."""
    trabalho = work_income(movements)
    if trabalho <= 0:
        return None
    return (trabalho - (gastos(movements) - devolucoes(movements))) / trabalho


def month_result(movements: Sequence[Movement]) -> Decimal:
    """Resultado do mês: receitas - gastos - investimento."""
    return receitas(movements) - gastos(movements) - investido(movements)
