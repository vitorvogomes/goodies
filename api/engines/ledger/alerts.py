"""Alertas do Ledger compute-on-read (STORY-01-08).

GET /cashflow/alerts avalia ao vivo (sem persistir): custos fixos vencendo em ≤5
dias + categorias acima de 120% da média dos últimos 3 meses. A persistência
(active_alerts) e o Alert Engine ficam para o m5.
"""

import datetime
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.ledger.service import (
    Alert,
    FixedCostDue,
    MonthCategoryTotal,
    category_overspend_alerts,
    upcoming_due_alerts,
)

router = APIRouter(prefix="/api/v1/cashflow", tags=["ledger:alerts"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


@router.get("/alerts", response_model=list[Alert])
async def alerts(user: AuthUser, db: Db) -> list[Alert]:
    today = datetime.date.today()

    fc_rows = await db.fetch(
        "SELECT name, amount, due_day, category FROM fixed_costs WHERE is_active"
    )
    fixed = [
        FixedCostDue(
            name=r["name"],
            amount=float(r["amount"]),
            due_day=r["due_day"],
            category=r["category"],
        )
        for r in fc_rows
    ]

    # Despesas por (mês, categoria) do mês atual + 3 meses anteriores (sem futuros).
    exp_rows = await db.fetch(
        """
        SELECT date_trunc('month', date)::date AS month, category, SUM(ABS(amount)) AS total
        FROM transactions
        WHERE amount < 0
          AND date >= (date_trunc('month', $1::date) - interval '3 months')
          AND date <  (date_trunc('month', $1::date) + interval '1 month')
        GROUP BY 1, 2
        """,
        today,
    )
    totals = [
        MonthCategoryTotal(month=r["month"], category=r["category"], total=float(r["total"]))
        for r in exp_rows
    ]

    return [*upcoming_due_alerts(fixed, today), *category_overspend_alerts(totals, today)]
