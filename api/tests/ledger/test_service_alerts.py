"""Lógica pura de alertas (STORY-01-08) — sem DB, today injetado."""

import datetime

from engines.ledger.service import (
    MonthCategoryTotal,
    category_overspend_alerts,
)


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
