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


class CategoryBreakdownRow(BaseModel):
    category: str
    total: float  # magnitude (sempre positivo)
    pct: float  # % do total da própria seção; 0 se a seção estiver vazia


class CategoryBreakdown(BaseModel):
    month: str | None
    income_total: float
    expense_total: float
    income: list[CategoryBreakdownRow]
    expense: list[CategoryBreakdownRow]


@router.get("/by-category")
async def by_category(
    user: AuthUser,
    db: Db,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> CategoryBreakdown:
    # Agrupa por categoria + lado (sinal do amount). % por seção via window function;
    # NULLIF evita divisão por zero. month opcional -> acumulado. Empty -> 200 vazio
    # (um breakdown de "nada" é significativo, ao contrário do savings rate).
    first: datetime.date | None = None
    nxt: datetime.date | None = None
    if month is not None:
        year, mon = int(month[:4]), int(month[5:7])
        first = datetime.date(year, mon, 1)
        nxt = datetime.date(year + mon // 12, mon % 12 + 1, 1)

    rows = await db.fetch(
        """
        WITH grouped AS (
          SELECT category,
                 CASE WHEN amount > 0 THEN 'income' ELSE 'expense' END AS side,
                 SUM(ABS(amount)) AS total
          FROM transactions
          WHERE ($1::date IS NULL OR date >= $1)
            AND ($2::date IS NULL OR date <  $2)
          GROUP BY category, side
        )
        SELECT category, side, total,
               ROUND(100 * total / NULLIF(SUM(total) OVER (PARTITION BY side), 0), 2) AS pct
        FROM grouped
        ORDER BY side, total DESC
        """,
        first,
        nxt,
    )

    income: list[CategoryBreakdownRow] = []
    expense: list[CategoryBreakdownRow] = []
    for r in rows:
        bucket = income if r["side"] == "income" else expense
        bucket.append(
            CategoryBreakdownRow(
                category=r["category"],
                total=float(r["total"]),
                pct=float(r["pct"]) if r["pct"] is not None else 0.0,
            )
        )
    return CategoryBreakdown(
        month=month,
        income_total=round(sum((r.total for r in income), 0.0), 2),
        expense_total=round(sum((r.total for r in expense), 0.0), 2),
        income=income,
        expense=expense,
    )


class ProjectionPoint(BaseModel):
    days: int
    fixed_income: float
    fixed_expenses: float
    projected_balance: float


class CashflowProjection(BaseModel):
    current_balance: float
    monthly_income: float
    monthly_expenses: float
    projections: list[ProjectionPoint]


@router.get("/projection")
async def projection(
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> CashflowProjection:
    # Saldo atual = soma de todas as transações (opc. por conta). Receita recorrente
    # mensal = is_recurring & amount>0. Despesa fixa mensal = custos fixos ativos.
    current_balance = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE ($1::uuid IS NULL OR account_id = $1)",
        account_id,
    )
    monthly_income = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE is_recurring AND amount > 0 AND ($1::uuid IS NULL OR account_id = $1)",
        account_id,
    )
    monthly_expenses = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM fixed_costs WHERE is_active"
    )
    cb = float(current_balance)
    mi = float(monthly_income)
    me = float(monthly_expenses)
    points = [
        ProjectionPoint(
            days=days,
            fixed_income=round(mi * (days // 30), 2),
            fixed_expenses=round(me * (days // 30), 2),
            projected_balance=round(cb + (mi - me) * (days // 30), 2),
        )
        for days in (30, 60, 90)
    ]
    return CashflowProjection(
        current_balance=round(cb, 2),
        monthly_income=round(mi, 2),
        monthly_expenses=round(me, 2),
        projections=points,
    )
