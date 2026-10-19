"""Receitas esperadas (Ajustes › Custos e receitas): o cadastro (nome, valor,
dia, pagador, vigência; "só neste mês" = vigência de um mês) e o recebido de cada uma no mês,
derivado na leitura das entradas do trabalho (`calc.match_expected_incomes`) — nada gravado."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated

import asyncpg
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from engines.common.dates import add_months, today_brt
from engines.common.deps import AuthUser, Db
from engines.common.models import Uuid
from engines.common.money import Money

from .calc import ExpectedIncome, IncomeTx, due_date, match_expected_incomes


class ExpectedIncomeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Annotated[Money, Field(gt=0)]
    due_day: int = Field(ge=1, le=31)
    payer: str | None = Field(default=None, max_length=120)
    valid_from: dt.date | None = None  # sem → mês atual
    only_month: bool = False  # receita de um mês só (pagamento a receber)


class ExpectedIncomePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Annotated[Money | None, Field(gt=0)] = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    payer: str | None = Field(default=None, max_length=120)  # "" limpa


class ExpectedIncomeRow(BaseModel):
    id: str
    name: str
    amount: Money
    due_day: int
    payer: str | None
    valid_from: dt.date
    valid_to: dt.date | None


class PlannedIncome(BaseModel):
    id: str
    name: str
    payer: str | None
    amount: Money
    due_date: dt.date
    received: Money
    pending: Money
    status: str  # recebido | parcial | a_receber | atrasado


class ExpectedIncomeNotFound(LookupError):
    pass


_ROW = "SELECT id, name, amount, due_day, payer, valid_from, valid_to FROM expected_incomes"


def _row(r: asyncpg.Record) -> ExpectedIncomeRow:
    return ExpectedIncomeRow(
        id=str(r["id"]),
        name=r["name"],
        amount=r["amount"],
        due_day=r["due_day"],
        payer=r["payer"],
        valid_from=r["valid_from"],
        valid_to=r["valid_to"],
    )


def _clean(payer: str | None) -> str | None:
    return (payer or "").strip() or None


async def list_incomes(conn: asyncpg.Connection) -> list[ExpectedIncomeRow]:
    """As vigentes hoje ou no futuro, por dia."""
    rows = await conn.fetch(
        _ROW + " WHERE valid_to IS NULL OR valid_to >= $1 ORDER BY valid_from, due_day, name",
        today_brt().replace(day=1),
    )
    return [_row(r) for r in rows]


async def _get(conn: asyncpg.Connection, income_id: str) -> ExpectedIncomeRow:
    row = await conn.fetchrow(_ROW + " WHERE id = $1::uuid", income_id)
    if row is None:
        raise ExpectedIncomeNotFound(income_id)
    return _row(row)


async def create_income(conn: asyncpg.Connection, body: ExpectedIncomeIn) -> ExpectedIncomeRow:
    start = (body.valid_from or today_brt()).replace(day=1)
    income_id = await conn.fetchval(
        "INSERT INTO expected_incomes (name, amount, due_day, payer, valid_from, valid_to) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        body.name.strip(),
        body.amount,
        body.due_day,
        _clean(body.payer),
        start,
        start if body.only_month else None,
    )
    return await _get(conn, str(income_id))


async def update_income(
    conn: asyncpg.Connection, income_id: str, body: ExpectedIncomePatch
) -> ExpectedIncomeRow:
    await _get(conn, income_id)
    await conn.execute(
        "UPDATE expected_incomes SET name = COALESCE($2, name), amount = COALESCE($3, amount), "
        "due_day = COALESCE($4, due_day), "
        "payer = CASE WHEN $5::text IS NULL THEN payer ELSE NULLIF(trim($5), '') END "
        "WHERE id = $1::uuid",
        income_id,
        body.name,
        body.amount,
        body.due_day,
        body.payer,
    )
    return await _get(conn, income_id)


async def delete_income(conn: asyncpg.Connection, income_id: str) -> None:
    """Como o custo fixo: encerra a vigência no mês anterior (os meses passados continuam com ela);
    a que só vale a partir deste mês é apagada."""
    income = await _get(conn, income_id)
    current = today_brt().replace(day=1)
    if income.valid_from >= current:
        await conn.execute("DELETE FROM expected_incomes WHERE id = $1::uuid", income_id)
    else:
        await conn.execute(
            "UPDATE expected_incomes SET valid_to = LEAST(COALESCE(valid_to, $2), $2) "
            "WHERE id = $1::uuid",
            income_id,
            add_months(current, -1),
        )


async def month_incomes(
    conn: asyncpg.Connection, month: dt.date, *, today: dt.date | None = None
) -> list[PlannedIncome]:
    """As receitas esperadas do mês com o recebido (entradas do trabalho do mês)."""
    if not await conn.fetchval("SELECT to_regclass('expected_incomes') IS NOT NULL"):
        return []  # base antiga (dados_reais migra passo a passo)
    rows = await conn.fetch(
        _ROW + " WHERE valid_from <= $1 AND (valid_to IS NULL OR valid_to >= $1) "
        "ORDER BY due_day, name",
        month,
    )
    if not rows:
        return []
    expected = [
        ExpectedIncome(
            str(r["id"]), r["name"], r["amount"], due_date(month, r["due_day"]), r["payer"]
        )
        for r in rows
    ]
    incomes = [
        IncomeTx(str(r["id"]), r["amount"], r["date"], r["description"] or "", r["payer"])
        for r in await conn.fetch(
            "SELECT t.id, t.amount, t.date, t.description, t.payer FROM transactions t "
            "JOIN categories c ON c.id = t.category_id WHERE c.role = 'work_income' "
            "AND t.amount > 0 AND t.date >= $1 AND t.date < $2",
            month,
            add_months(month, 1),
        )
    ]
    found = {
        m.income_id: m for m in match_expected_incomes(expected, incomes, today or today_brt())
    }
    return [
        PlannedIncome(
            id=e.income_id,
            name=e.name,
            payer=e.payer,
            amount=e.amount,
            due_date=e.due,
            received=found[e.income_id].received,
            pending=found[e.income_id].pending,
            status=found[e.income_id].status,
        )
        for e in expected
    ]


def planned_totals(items: list[PlannedIncome]) -> tuple[Decimal, Decimal]:
    """(planejado, a receber) do mês."""
    return (
        sum((i.amount for i in items), Decimal(0)),
        sum((i.pending for i in items), Decimal(0)),
    )


router = APIRouter(prefix="/api/v1/ledger/expected-incomes", tags=["ledger:receitas"])
_NOT_FOUND = {"error": "receita_inexistente", "message": "Receita esperada não existe."}


@router.get("", response_model=list[ExpectedIncomeRow])
async def list_route(user: AuthUser, db: Db) -> list[ExpectedIncomeRow]:
    return await list_incomes(db)


@router.post("", response_model=ExpectedIncomeRow, status_code=status.HTTP_201_CREATED)
async def create_route(body: ExpectedIncomeIn, user: AuthUser, db: Db) -> ExpectedIncomeRow:
    return await create_income(db, body)


@router.patch("/{income_id}", response_model=ExpectedIncomeRow)
async def update_route(
    income_id: Uuid, body: ExpectedIncomePatch, user: AuthUser, db: Db
) -> ExpectedIncomeRow:
    try:
        return await update_income(db, str(income_id), body)
    except ExpectedIncomeNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(income_id: Uuid, user: AuthUser, db: Db) -> None:
    try:
        await delete_income(db, str(income_id))
    except ExpectedIncomeNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None
