"""Núcleo puro do ledger (AD-2: Decimal, sem IO).

Story 2.5 — escolha da regra de categoria (AD-6): "descrição contém", com direção pelo sinal
(entrada > 0, saída < 0, ambos); vence a condição mais longa; empate → a regra mais recente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import pairwise

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


# --------------------------------------------------------------------------------------------
# Conferência encadeada do saldo da conta PF (Story 3.12 — FR-5, AR14)
# --------------------------------------------------------------------------------------------

CENT_TOLERANCE = Decimal("0.005")


@dataclass(frozen=True)
class BalanceInterval:
    """Entre dois saldos informados: anterior + Σ transações de (start, end] = informado."""

    start: date
    end: date
    previous: Decimal
    movement: Decimal
    reported: Decimal

    @property
    def expected(self) -> Decimal:
        return self.previous + self.movement

    @property
    def difference(self) -> Decimal:
        return (self.reported - self.expected).quantize(Decimal("0.01"))

    @property
    def ok(self) -> bool:
        return abs(self.reported - self.expected) < CENT_TOLERANCE


def opening_balance(
    anchor_reported: Decimal, anchor_date: date, transactions: Sequence[tuple[date, Decimal]]
) -> Decimal:
    """Saldo de abertura = saldo informado na âncora − Σ transações até a data da âncora."""
    return anchor_reported - sum((a for d, a in transactions if d <= anchor_date), Decimal(0))


def chained_check(
    reported: Sequence[tuple[date, Decimal]], transactions: Sequence[tuple[date, Decimal]]
) -> list[BalanceInterval]:
    """Um intervalo por par de saldos informados consecutivos; cada um parte do saldo **informado**
    anterior, então um erro antigo fica isolado no intervalo em que aconteceu."""
    ordered = sorted(reported)
    intervals: list[BalanceInterval] = []
    for (start, previous), (end, current) in pairwise(ordered):
        movement = sum((a for d, a in transactions if start < d <= end), Decimal(0))
        intervals.append(BalanceInterval(start, end, previous, movement, current))
    return intervals


def month_checked(intervals: Sequence[BalanceInterval], month_end: date) -> bool:
    """Mês conferido: vale o primeiro saldo informado com data ≥ fim do mês, desde que todos os
    intervalos até ele batam (o OFX semanal não precisa terminar no último dia)."""
    for i, interval in enumerate(intervals):
        if interval.end >= month_end:
            return all(x.ok for x in intervals[: i + 1])
    return False
