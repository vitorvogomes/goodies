"""Serviço do Ledger: avaliação de alertas v1 (STORY-01-08, puros) e `categorize()`, o caminho
único de mudança de categoria (Story 2.5 — AD-6).

As funções de alerta recebem `today` injetado -> determinísticas e testáveis sem relógio nem DB.
"""

import calendar
import datetime
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

import asyncpg
from pydantic import BaseModel

from engines.common.month_status import month_status

from . import queries
from .calc import Movement, Rule, savings_rate
from .models import KIND_LABEL, CategoryOption, TransactionList, TransactionRow

AlertData = dict[str, float | int | str]


class Alert(BaseModel):
    type: str
    severity: str
    title: str
    message: str
    data: AlertData


@dataclass
class FixedCostDue:
    name: str
    amount: float
    due_day: int
    category: str


@dataclass
class MonthCategoryTotal:
    month: datetime.date  # primeiro dia do mês
    category: str
    total: float  # magnitude da despesa (positivo)


def _occurrence(year: int, month: int, due_day: int) -> datetime.date:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(due_day, last))


def _next_occurrence(due_day: int, today: datetime.date) -> datetime.date:
    this_month = _occurrence(today.year, today.month, due_day)
    if this_month >= today:
        return this_month
    if today.month == 12:
        return _occurrence(today.year + 1, 1, due_day)
    return _occurrence(today.year, today.month + 1, due_day)


def upcoming_due_alerts(
    items: list[FixedCostDue], today: datetime.date, horizon: int = 5
) -> list[Alert]:
    """Custos fixos com vencimento nos próximos `horizon` dias."""
    alerts: list[Alert] = []
    for fc in items:
        days_until = (_next_occurrence(fc.due_day, today) - today).days
        if 0 <= days_until <= horizon:
            alerts.append(
                Alert(
                    type="fixed_cost_due",
                    severity="warning",
                    title="Custo fixo vencendo",
                    message=f"{fc.name} vence em {days_until} dia(s) (dia {fc.due_day})",
                    data={
                        "name": fc.name,
                        "amount": round(fc.amount, 2),
                        "due_day": fc.due_day,
                        "days_until": days_until,
                    },
                )
            )
    return alerts


def _month_minus(month_start: datetime.date, n: int) -> datetime.date:
    total = (month_start.year * 12 + (month_start.month - 1)) - n
    return datetime.date(total // 12, total % 12 + 1, 1)


def category_overspend_alerts(
    rows: list[MonthCategoryTotal], today: datetime.date, factor: float = 1.2
) -> list[Alert]:
    """Categorias cujo gasto do mês atual passa de `factor`x a média dos 3 meses anteriores."""
    current = datetime.date(today.year, today.month, 1)
    prev_months = {_month_minus(current, n) for n in (1, 2, 3)}

    current_by_cat: dict[str, float] = {}
    prev_by_cat: dict[str, float] = {}
    for r in rows:
        if r.month == current:
            current_by_cat[r.category] = current_by_cat.get(r.category, 0.0) + r.total
        elif r.month in prev_months:
            prev_by_cat[r.category] = prev_by_cat.get(r.category, 0.0) + r.total

    alerts: list[Alert] = []
    for category, current_total in current_by_cat.items():
        if category not in prev_by_cat:
            continue
        avg = prev_by_cat[category] / 3  # meses ausentes contam como 0
        if avg > 0 and current_total > factor * avg:
            pct = round((current_total / avg - 1) * 100)
            alerts.append(
                Alert(
                    type="category_overspend",
                    severity="warning",
                    title="Categoria acima da média",
                    message=(
                        f"Categoria '{category}' está {pct}% acima da "
                        "média dos últimos 3 meses"
                    ),
                    data={
                        "category": category,
                        "current": round(current_total, 2),
                        "avg_3m": round(avg, 2),
                        "pct_above": pct,
                    },
                )
            )
    return alerts


# --------------------------------------------------------------------------------------------
# Categorização por um caminho só (Story 2.5 — AD-6)
# --------------------------------------------------------------------------------------------

Source = Literal["rule", "suggestion", "manual"]
Cause = Literal[
    "import", "review", "inline_edit", "rule_created", "reapply", "move", "migration", "undo"
]
TransactionsChangedHook = Callable[[asyncpg.Connection, list[str]], Awaitable[None]]

_hooks: list[TransactionsChangedHook] = []


def register_on_transactions_changed(hook: TransactionsChangedHook) -> None:
    """Engines de cima (portfolio) registram a derivação em `main.py` (AD-1/AD-6)."""
    _hooks.append(hook)


def clear_transaction_hooks() -> None:
    _hooks.clear()


@dataclass(frozen=True)
class CategoryChange:
    transaction_id: str
    category_id: str
    source: Source
    rule_id: str | None = None


@dataclass
class CategorizeResult:
    changed: list[str] = field(default_factory=list)
    kept_manual: list[str] = field(default_factory=list)


async def load_rules(conn: asyncpg.Connection) -> list[Rule]:
    return [
        Rule(
            pattern=r["pattern"],
            direction=r["direction"],
            category_id=str(r["category_id"]),
            category_name=r["category_name"],
            kind=r["kind"],
            rule_id=str(r["id"]),
            created_at=r["created_at"],
        )
        for r in await queries.active_rules(conn)
    ]


async def categorize(
    conn: asyncpg.Connection,
    changes: Sequence[CategoryChange],
    *,
    cause: Cause,
    batch_id: str | None = None,
    review_status: Literal["pending", "confirmed"] | None = None,
    fire_hooks: bool = True,
) -> CategorizeResult:
    """Único caminho de mudança de categoria (AD-6). Roda na transação de quem chama.

    Grava `category_id`, a cópia de `kind` do grupo, a coluna de texto (esquema duplo até a 10.6),
    `category_source` e a regra; registra o evento; marca o mês sujo; chama os hooks. Categoria
    `manual` nunca é sobrescrita por regra ou sugestão.
    """
    result = CategorizeResult()
    if not changes:
        return result
    tx_ids = [c.transaction_id for c in changes]
    state = {str(r["id"]): r for r in await conn.fetch(queries.TX_STATE, tx_ids)}
    cats = {
        str(r["id"]): r
        for r in await conn.fetch(queries.CATEGORY_INFO, list({c.category_id for c in changes}))
    }
    months: set[date] = set()
    for ch in changes:
        current = state.get(ch.transaction_id)
        if current is None:
            raise LookupError(f"transação inexistente: {ch.transaction_id}")
        cat = cats.get(ch.category_id)
        if cat is None:
            raise LookupError(f"categoria inexistente: {ch.category_id}")
        if current["category_source"] == "manual" and ch.source != "manual":
            result.kept_manual.append(ch.transaction_id)
            continue
        before = str(current["category_id"]) if current["category_id"] else None
        rule_id = ch.rule_id if ch.source == "rule" else None
        if (
            before == ch.category_id
            and current["category_source"] == ch.source
            and (review_status is None or review_status == current["review_status"])
        ):
            continue  # nada muda: sem evento
        await conn.execute(
            queries.APPLY_CATEGORY,
            ch.transaction_id,
            ch.category_id,
            cat["name"],
            cat["kind"],
            ch.source,
            rule_id,
            review_status,
        )
        await conn.execute(
            queries.INSERT_EVENT,
            ch.transaction_id,
            before,
            ch.category_id,
            ch.source,
            cause,
            batch_id,
            rule_id,
        )
        result.changed.append(ch.transaction_id)
        months.add(current["date"].replace(day=1))
    port = month_status()
    for month in sorted(months):
        await port.mark_dirty(conn, month)
    if fire_hooks and result.changed:
        for hook in _hooks:
            await hook(conn, list(result.changed))
    return result


async def monthly_savings(
    conn: asyncpg.Connection, months: Sequence[date] | None = None
) -> dict[date, Decimal | None]:
    """Taxa de poupança (fração) por mês pela função única de `ledger/calc` (Story 2.6, AD-7).
    Mês sem receita do trabalho → None."""
    by_month: dict[date, list[Movement]] = {}
    for r in await queries.month_movements(conn, months):
        by_month.setdefault(r["month"], []).append(Movement(r["amount"], r["kind"], r["role"]))
    return {m: savings_rate(mv) for m, mv in sorted(by_month.items())}


# --------------------------------------------------------------------------------------------
# Caixa › Transações (Story 2.7)
# --------------------------------------------------------------------------------------------


def to_row(r: asyncpg.Record) -> TransactionRow:
    return TransactionRow(
        id=str(r["id"]),
        date=r["date"],
        description=r["description"],
        amount=r["amount"],
        kind=r["kind"],
        kind_label=KIND_LABEL.get(r["kind"], r["kind"]),
        category_id=str(r["category_id"]),
        category_name=r["category_name"],
        category_key=r["category_key"],
        group_name=r["group_name"],
        category_source=r["category_source"],
        review_status=r["review_status"],
        payer=r["payer"],
        account_id=str(r["account_id"]),
        account_name=r["account_name"],
        source=r["source"],
        batch_id=str(r["batch_id"]) if r["batch_id"] else None,
        file_name=r["file_name"],
        rule_pattern=r["rule_pattern"],
    )


async def list_transactions(
    conn: asyncpg.Connection, month: date, limit: int, offset: int
) -> TransactionList:
    end = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    rows, total = await queries.transactions_page(conn, month, end, limit, offset)
    return TransactionList(items=[to_row(r) for r in rows], total=total, limit=limit, offset=offset)


async def set_category_manual(
    conn: asyncpg.Connection, tx_id: str, category_id: str
) -> TransactionRow | None:
    """Correção na linha: categorize() com origem manual, confirmada (Story 2.7)."""
    if not await queries.category_exists(conn, category_id):
        raise LookupError("categoria")
    async with conn.transaction():
        if await queries.transaction_row(conn, tx_id) is None:
            return None
        await categorize(
            conn,
            [CategoryChange(tx_id, category_id, "manual")],
            cause="inline_edit",
            review_status="confirmed",
        )
    row = await queries.transaction_row(conn, tx_id)
    return to_row(row) if row is not None else None


async def category_options(
    conn: asyncpg.Connection, include_archived: bool = False
) -> list[CategoryOption]:
    return [
        CategoryOption(
            id=str(r["id"]),
            key=r["key"],
            name=r["name"],
            label=f"{r['group_name']} › {r['name']}",
            group_key=r["group_key"],
            group_name=r["group_name"],
            kind=r["kind"],
            role=r["role"],
            is_active=r["is_active"],
        )
        for r in await queries.category_options(conn, include_archived)
    ]
