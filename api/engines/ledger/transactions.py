"""CRUD de transações + validação + filtros/paginação (STORY-01-03).

amount: positivo = receita, negativo = despesa (nunca zero). account_id deve
existir (FK → 422). Lista paginada com filtros from/to/category/account_id.
NUMERIC(15,2) no banco; a API transporta float (cálculos autoritativos ficam em
SQL — ver view monthly_summary).
"""

import datetime
import uuid
from decimal import Decimal
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from auth.dependencies import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api/v1/transactions", tags=["ledger:transactions"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    date: datetime.date
    amount: float
    category: str = Field(min_length=1)
    description: str | None = None
    is_recurring: bool = False
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("amount não pode ser zero (positivo=receita, negativo=despesa)")
        return v


class TransactionUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    date: datetime.date | None = None
    amount: float | None = None
    category: str | None = Field(default=None, min_length=1)
    description: str | None = None
    is_recurring: bool | None = None
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v: float | None) -> float | None:
        if v is not None and v == 0:
            raise ValueError("amount não pode ser zero")
        return v


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    date: str
    amount: float
    category: str
    description: str | None
    is_recurring: bool
    external_id: str | None
    notes: str | None


class TransactionList(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
    total_income: float  # soma das receitas do conjunto filtrado (não só da página)
    total_expense: float  # soma das despesas (magnitude) do conjunto filtrado


_COLUMNS = (
    "id, account_id, date, amount, category, description, is_recurring, external_id, notes"
)


def _to_response(row: asyncpg.Record) -> TransactionResponse:
    return TransactionResponse(
        id=str(row["id"]),
        account_id=str(row["account_id"]),
        date=row["date"].isoformat(),
        amount=float(row["amount"]),
        category=row["category"],
        description=row["description"],
        is_recurring=row["is_recurring"],
        external_id=row["external_id"],
        notes=row["notes"],
    )


def _as_decimal(amount: float | None) -> Decimal | None:
    # str() evita ruído binário do float; NUMERIC(15,2) arredonda p/ 2 casas.
    return Decimal(str(amount)) if amount is not None else None


@router.get("", response_model=TransactionList)
async def list_transactions(
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    from_: Annotated[datetime.date | None, Query(alias="from")] = None,
    to: Annotated[datetime.date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionList:
    where = (
        "WHERE ($1::uuid IS NULL OR account_id = $1) "
        "AND ($2::text IS NULL OR category = $2) "
        "AND ($3::date IS NULL OR date >= $3) "
        "AND ($4::date IS NULL OR date <= $4)"
    )
    agg = await db.fetchrow(
        "SELECT count(*) AS total, "
        "COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) AS income, "
        "COALESCE(SUM(-amount) FILTER (WHERE amount < 0), 0) AS expense "
        f"FROM transactions {where}",
        account_id,
        category,
        from_,
        to,
    )
    rows = await db.fetch(
        f"SELECT {_COLUMNS} FROM transactions {where} "
        "ORDER BY date DESC, created_at DESC LIMIT $5 OFFSET $6",
        account_id,
        category,
        from_,
        to,
        limit,
        offset,
    )
    return TransactionList(
        items=[_to_response(r) for r in rows],
        total=agg["total"],
        limit=limit,
        offset=offset,
        total_income=float(agg["income"]),
        total_expense=float(agg["expense"]),
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreate, user: AuthUser, db: Db
) -> TransactionResponse:
    try:
        row = await db.fetchrow(
            "INSERT INTO transactions "
            "(account_id, date, amount, category, description, is_recurring, notes) "
            f"VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING {_COLUMNS}",
            body.account_id,
            body.date,
            _as_decimal(body.amount),
            body.category,
            body.description,
            body.is_recurring,
            body.notes,
        )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conta inexistente") from None
    return _to_response(row)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID, body: TransactionUpdate, user: AuthUser, db: Db
) -> TransactionResponse:
    try:
        row = await db.fetchrow(
            """
            UPDATE transactions SET
              account_id = COALESCE($2, account_id),
              date = COALESCE($3, date),
              amount = COALESCE($4, amount),
              category = COALESCE($5, category),
              description = COALESCE($6, description),
              is_recurring = COALESCE($7, is_recurring),
              notes = COALESCE($8, notes)
            WHERE id = $1
            """
            f" RETURNING {_COLUMNS}",
            transaction_id,
            body.account_id,
            body.date,
            _as_decimal(body.amount),
            body.category,
            body.description,
            body.is_recurring,
            body.notes,
        )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conta inexistente") from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
    return _to_response(row)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute("DELETE FROM transactions WHERE id = $1", transaction_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
