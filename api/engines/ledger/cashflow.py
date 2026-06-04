"""Saldo running + resumo mensal + taxa de poupança (STORY-01-04 / 01-05).

GET /cashflow            -> lançamentos com saldo running (window SUM).
GET /cashflow/summary    -> resumo mensal (view monthly_summary). Com ?month=YYYY-MM
                            retorna um único mês; 404 se sem dados; 422 se receita=0.

savings_rate = (receita - despesa)/receita * 100 (ja calculado na view). Nota: a
view trata QUALQUER amount<0 como despesa — o import (01-13-14) NÃO grava
investimento/transferência interna como transação, senão a taxa distorce.
"""

import datetime
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api/v1/cashflow", tags=["ledger:cashflow"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]

_SUMMARY_SELECT = (
    "SELECT month, total_income, total_expense, net_cashflow, savings_rate FROM monthly_summary"
)


class MonthlySummary(BaseModel):
    month: str
    total_income: float
    total_expense: float
    net_cashflow: float
    savings_rate: float


class CashflowEntry(BaseModel):
    id: str
    account_id: str
    date: str
    amount: float
    category: str
    description: str | None
    running_balance: float


def _summary(row: asyncpg.Record) -> MonthlySummary:
    return MonthlySummary(
        month=row["month"].strftime("%Y-%m"),
        total_income=float(row["total_income"]),
        total_expense=float(row["total_expense"]),
        net_cashflow=float(row["net_cashflow"]),
        savings_rate=round(float(row["savings_rate"]), 2),
    )


@router.get("")
async def cashflow(
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    from_: Annotated[datetime.date | None, Query(alias="from")] = None,
    to: Annotated[datetime.date | None, Query()] = None,
) -> list[CashflowEntry]:
    rows = await db.fetch(
        """
        SELECT id, account_id, date, amount, category, description,
               SUM(amount) OVER (
                 ORDER BY date, created_at
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
               ) AS running_balance
        FROM transactions
        WHERE ($1::uuid IS NULL OR account_id = $1)
          AND ($2::date IS NULL OR date >= $2)
          AND ($3::date IS NULL OR date <= $3)
        ORDER BY date, created_at
        """,
        account_id,
        from_,
        to,
    )
    return [
        CashflowEntry(
            id=str(r["id"]),
            account_id=str(r["account_id"]),
            date=r["date"].isoformat(),
            amount=float(r["amount"]),
            category=r["category"],
            description=r["description"],
            running_balance=float(r["running_balance"]),
        )
        for r in rows
    ]


@router.get("/summary")
async def summary(
    user: AuthUser,
    db: Db,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> MonthlySummary | list[MonthlySummary]:
    if month is None:
        rows = await db.fetch(_SUMMARY_SELECT)
        return [_summary(r) for r in rows]

    first = datetime.date(int(month[:4]), int(month[5:7]), 1)
    row = await db.fetchrow(
        _SUMMARY_SELECT + " WHERE month = date_trunc('month', $1::date)", first
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sem dados para o mês informado")
    if float(row["total_income"]) == 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "zero_income",
                "message": "receita do período é zero; taxa de poupança indefinida",
            },
        )
    return _summary(row)
