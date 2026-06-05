"""CRUD de custos fixos (STORY-01-07).

Custos recorrentes com dia de vencimento (1-31). Alimentam a projeção de caixa
(01-06) e os alertas de vencimento (01-08). amount > 0 (magnitude do custo).
"""

import uuid
from decimal import Decimal
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api/v1/fixed-costs", tags=["ledger:fixed-costs"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]

_COLUMNS = "id, name, amount, due_day, category, is_active"


class FixedCostCreate(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    due_day: int = Field(ge=1, le=31)
    category: str = Field(min_length=1)
    is_active: bool = True


class FixedCostUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    amount: float | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    category: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class FixedCostResponse(BaseModel):
    id: str
    name: str
    amount: float
    due_day: int
    category: str
    is_active: bool


def _to_response(row: asyncpg.Record) -> FixedCostResponse:
    return FixedCostResponse(
        id=str(row["id"]),
        name=row["name"],
        amount=float(row["amount"]),
        due_day=row["due_day"],
        category=row["category"],
        is_active=row["is_active"],
    )


def _as_decimal(amount: float | None) -> Decimal | None:
    return Decimal(str(amount)) if amount is not None else None


@router.get("", response_model=list[FixedCostResponse])
async def list_fixed_costs(
    user: AuthUser,
    db: Db,
    active: Annotated[bool | None, Query()] = None,
) -> list[FixedCostResponse]:
    rows = await db.fetch(
        f"SELECT {_COLUMNS} FROM fixed_costs "
        "WHERE ($1::boolean IS NULL OR is_active = $1) "
        "ORDER BY due_day, name",
        active,
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=FixedCostResponse, status_code=status.HTTP_201_CREATED)
async def create_fixed_cost(body: FixedCostCreate, user: AuthUser, db: Db) -> FixedCostResponse:
    row = await db.fetchrow(
        "INSERT INTO fixed_costs (name, amount, due_day, category, is_active) "
        f"VALUES ($1, $2, $3, $4, $5) RETURNING {_COLUMNS}",
        body.name,
        _as_decimal(body.amount),
        body.due_day,
        body.category,
        body.is_active,
    )
    return _to_response(row)


@router.put("/{fixed_cost_id}", response_model=FixedCostResponse)
async def update_fixed_cost(
    fixed_cost_id: uuid.UUID, body: FixedCostUpdate, user: AuthUser, db: Db
) -> FixedCostResponse:
    row = await db.fetchrow(
        """
        UPDATE fixed_costs SET
          name = COALESCE($2, name),
          amount = COALESCE($3, amount),
          due_day = COALESCE($4, due_day),
          category = COALESCE($5, category),
          is_active = COALESCE($6, is_active)
        WHERE id = $1
        """
        f" RETURNING {_COLUMNS}",
        fixed_cost_id,
        body.name,
        _as_decimal(body.amount),
        body.due_day,
        body.category,
        body.is_active,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "custo fixo não encontrado")
    return _to_response(row)


@router.delete("/{fixed_cost_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixed_cost(fixed_cost_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute("DELETE FROM fixed_costs WHERE id = $1", fixed_cost_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "custo fixo não encontrado")
