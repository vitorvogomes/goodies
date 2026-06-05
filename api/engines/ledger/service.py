"""Lógica pura do Ledger: avaliação de alertas (STORY-01-08), sem I/O.

As funções recebem `today` injetado -> determinísticas e testáveis sem relógio
nem DB. Alertas compute-on-read; persistência (active_alerts) fica para o m5.
"""

import calendar
import datetime
from dataclasses import dataclass

from pydantic import BaseModel

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
