"""Lógica pura de alertas (STORY-01-08) — sem DB, today injetado."""

import datetime

from engines.ledger.service import (
    FixedCostDue,
    MonthCategoryTotal,
    category_overspend_alerts,
    upcoming_due_alerts,
)


def test_upcoming_due_within_horizon():
    today = datetime.date(2026, 6, 4)
    items = [
        FixedCostDue(name="Aluguel", amount=1500, due_day=6, category="moradia"),  # 2 dias
        FixedCostDue(name="Internet", amount=100, due_day=4, category="assinaturas"),  # hoje
        FixedCostDue(name="Cartao", amount=900, due_day=20, category="outros"),  # longe
    ]
    alerts = upcoming_due_alerts(items, today, horizon=5)
    assert {a.data["name"] for a in alerts} == {"Aluguel", "Internet"}
    assert all(a.type == "fixed_cost_due" and a.severity == "warning" for a in alerts)


def test_due_day_already_passed_not_alerted():
    today = datetime.date(2026, 6, 4)
    # dia 2 já passou neste mês; próxima ocorrência é Jul/02 (28 dias) -> sem alerta
    items = [FixedCostDue(name="X", amount=10, due_day=2, category="c")]
    assert upcoming_due_alerts(items, today, horizon=5) == []


def test_due_day_clamped_to_end_of_month():
    today = datetime.date(2026, 6, 27)
    # dia 31 em junho (30 dias) -> clampa p/ 30 = 3 dias -> alerta
    items = [FixedCostDue(name="Fatura", amount=500, due_day=31, category="outros")]
    alerts = upcoming_due_alerts(items, today, horizon=5)
    assert len(alerts) == 1
    assert alerts[0].data["days_until"] == 3


def test_category_overspend_detected():
    today = datetime.date(2026, 6, 15)
    cur = datetime.date(2026, 6, 1)
    prev = [datetime.date(2026, 5, 1), datetime.date(2026, 4, 1), datetime.date(2026, 3, 1)]
    rows = [
        MonthCategoryTotal(month=cur, category="alimentacao", total=600),
        *[MonthCategoryTotal(month=m, category="alimentacao", total=400) for m in prev],
        MonthCategoryTotal(month=cur, category="transporte", total=100),
        *[MonthCategoryTotal(month=m, category="transporte", total=100) for m in prev],
    ]
    alerts = category_overspend_alerts(rows, today, factor=1.2)
    # alimentacao: 600 > 1.2*400=480 -> alerta; transporte: 100 == média -> não
    assert {a.data["category"] for a in alerts} == {"alimentacao"}
    assert alerts[0].type == "category_overspend"


def test_category_overspend_no_baseline_skipped():
    today = datetime.date(2026, 6, 15)
    rows = [MonthCategoryTotal(month=datetime.date(2026, 6, 1), category="novo", total=999)]
    assert category_overspend_alerts(rows, today) == []
