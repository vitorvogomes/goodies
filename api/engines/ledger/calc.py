"""Núcleo puro do ledger (AD-2: Decimal, sem IO).

Story 2.5 — escolha da regra de categoria (AD-6): "descrição contém", com direção pelo sinal
(entrada > 0, saída < 0, ambos); vence a condição mais longa; empate → a regra mais recente.
"""

from __future__ import annotations

import calendar
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
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
    moves = sorted(transactions)
    days = [d for d, _ in moves]
    cumulative = [Decimal(0)]
    for _, amount in moves:
        cumulative.append(cumulative[-1] + amount)

    def through(day: date) -> Decimal:  # Σ transações com data ≤ day
        return cumulative[bisect_right(days, day)]

    intervals: list[BalanceInterval] = []
    for (start, previous), (end, current) in pairwise(ordered):
        intervals.append(
            BalanceInterval(start, end, previous, through(end) - through(start), current)
        )
    return intervals


def month_checked(intervals: Sequence[BalanceInterval], month_end: date) -> bool:
    """Mês conferido: vale o primeiro saldo informado com data ≥ fim do mês, desde que todos os
    intervalos até ele batam (o OFX semanal não precisa terminar no último dia)."""
    for i, interval in enumerate(intervals):
        if interval.end >= month_end:
            return all(x.ok for x in intervals[: i + 1])
    return False


def computed_balance(
    opening: Decimal, transactions: Sequence[tuple[date, Decimal]], until: date
) -> Decimal:
    """Saldo calculado (AD-7): saldo de abertura + Σ transações até a data."""
    return opening + sum((a for d, a in transactions if d <= until), Decimal(0))


# --------------------------------------------------------------------------------------------
# Casamento de custo fixo (Story 6.1 — AD-7, AD-9)
# --------------------------------------------------------------------------------------------

MATCH_VALUE_TOLERANCE = Decimal("0.10")  # ±10% do valor cadastrado
MATCH_DAYS_BEFORE = 5  # até 5 dias antes do vencimento
MATCH_DAYS_AFTER = 5  # até 5 dias depois


@dataclass(frozen=True)
class CostDue:
    cost_id: str
    amount: Decimal  # valor cadastrado (positivo)
    due: date  # vencimento no mês


@dataclass(frozen=True)
class TxCandidate:
    transaction_id: str
    amount: Decimal  # magnitude da saída (positivo)
    date: date


@dataclass(frozen=True)
class Decision:
    """Decisão humana gravada em `fixed_cost_payments`: confirmado/corrigido (com a transação),
    manual (pago sem transação) ou desfeito (aquela transação não é deste custo)."""

    cost_id: str
    kind: str  # confirmado | corrigido | manual | desfeito
    transaction_id: str | None


@dataclass(frozen=True)
class CostMatch:
    cost_id: str
    status: str  # pago | manual | pendente
    transaction_id: str | None = None
    source: str | None = None  # decisao | auto
    candidates: list[str] = field(default_factory=list)  # "2 candidatas": nada pago até escolher


def due_date(month: date, due_day: int) -> date:
    """Vencimento no mês; dia além do fim do mês cai no último dia."""
    last = calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=min(due_day, last))


def _eligible(cost: CostDue, tx: TxCandidate) -> bool:
    if abs(tx.amount - cost.amount) > cost.amount * MATCH_VALUE_TOLERANCE:
        return False
    return -MATCH_DAYS_BEFORE <= (tx.date - cost.due).days <= MATCH_DAYS_AFTER


def match_fixed_costs(
    costs: Sequence[CostDue], txs: Sequence[TxCandidate], decisions: Sequence[Decision]
) -> dict[str, CostMatch]:
    """Decisões primeiro; depois o guloso global 1:1 por (|Δvalor|, |Δdata|, custo, transação).
    Um custo que, depois do guloso, ainda tem outra candidata livre fica pendente com as candidatas
    (casamento ambíguo: nada pago até a escolha)."""
    out: dict[str, CostMatch] = {}
    tx_ids = {t.transaction_id for t in txs}
    taken: set[str] = set()
    rejected: set[tuple[str, str]] = set()
    for d in decisions:
        if d.kind == "desfeito":
            if d.transaction_id is not None:
                rejected.add((d.cost_id, d.transaction_id))
        elif d.kind == "manual":
            out[d.cost_id] = CostMatch(d.cost_id, "manual", source="decisao")
        elif d.transaction_id is not None and d.transaction_id in tx_ids:
            out[d.cost_id] = CostMatch(d.cost_id, "pago", d.transaction_id, "decisao")
            taken.add(d.transaction_id)
    free_costs = [c for c in costs if c.cost_id not in out]
    pairs = sorted(
        (
            (abs(t.amount - c.amount), abs((t.date - c.due).days), c.cost_id, t.transaction_id)
            for c in free_costs
            for t in txs
            if t.transaction_id not in taken
            and (c.cost_id, t.transaction_id) not in rejected
            and _eligible(c, t)
        ),
    )
    eligible: dict[str, list[str]] = {}
    for *_, cid, tid in pairs:
        eligible.setdefault(cid, []).append(tid)
    auto: dict[str, str] = {}
    for *_, cid, tid in pairs:
        if cid not in auto and tid not in taken:
            auto[cid] = tid
            taken.add(tid)
    for c in free_costs:
        chosen = auto.get(c.cost_id)
        others = [t for t in eligible.get(c.cost_id, []) if t not in taken]
        if chosen is not None and not others:
            out[c.cost_id] = CostMatch(c.cost_id, "pago", chosen, "auto")
        elif chosen is not None:
            out[c.cost_id] = CostMatch(c.cost_id, "pendente", candidates=sorted([chosen, *others]))
        else:
            out[c.cost_id] = CostMatch(c.cost_id, "pendente")
    return out


# --------------------------------------------------------------------------------------------
# Consumido (Story 6.5 — AD-7): gastos − deduções, cada transação num balde só
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SpendTx:
    transaction_id: str
    amount: Decimal  # com sinal
    kind: str
    role: str


@dataclass(frozen=True)
class Consumed:
    gastos: Decimal  # gastos brutos do mês (kind expense, magnitude)
    fixos: Decimal  # pagamentos casados a custo fixo
    dividas: Decimal  # role `divida` não casada a custo fixo
    devolucoes: Decimal  # role `devolucao` (entrada)

    @property
    def total(self) -> Decimal:
        return self.gastos - self.fixos - self.dividas - self.devolucoes


def consumido(spend: Sequence[SpendTx], matched_fixed: set[str]) -> Consumed:
    """Consumido = gastos − deduções; o balde de cada transação, nessa ordem: custo fixo casado >
    dívida > devolução."""
    gastos_ = fixos = dividas = devolucoes_ = Decimal(0)
    for t in spend:
        if t.kind == "expense":
            gastos_ -= t.amount
            if t.transaction_id in matched_fixed:
                fixos -= t.amount
            elif t.role == "divida":
                dividas -= t.amount
        elif t.role == "devolucao":
            devolucoes_ += t.amount
    return Consumed(gastos_, fixos, dividas, devolucoes_)
