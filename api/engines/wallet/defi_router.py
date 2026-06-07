"""CRUD de posições DeFi (entrada manual, ADR-004) — STORY-04-08.

Posições DeFi (Phantom) que não vêm de scan on-chain (xSOL/hyUSD com vencimento).
`/api/v1/defi/positions` (POST/GET/PUT/DELETE), escopo por usuário. Os alertas de
vencimento (04-09) leem desta tabela.
"""
import datetime
import uuid
from decimal import Decimal
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.ledger.service import Alert
from engines.wallet.defi import DefiMaturity, defi_maturity_alerts

router = APIRouter(prefix="/api/v1/defi", tags=["wallet:defi"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]

_COLUMNS = "id, protocol, asset_symbol, balance, maturity_date, is_active, notes"


class DefiPositionCreate(BaseModel):
    asset_symbol: str = Field(min_length=1)
    balance: float = Field(ge=0)
    protocol: str | None = None
    maturity_date: datetime.date | None = None
    is_active: bool = True
    notes: str | None = None


class DefiPositionUpdate(BaseModel):
    asset_symbol: str | None = Field(default=None, min_length=1)
    balance: float | None = Field(default=None, ge=0)
    protocol: str | None = None
    maturity_date: datetime.date | None = None
    is_active: bool | None = None
    notes: str | None = None


class DefiPositionResponse(BaseModel):
    id: str
    asset_symbol: str
    balance: float
    protocol: str | None
    maturity_date: datetime.date | None
    is_active: bool
    notes: str | None


def _to_response(row: asyncpg.Record) -> DefiPositionResponse:
    return DefiPositionResponse(
        id=str(row["id"]),
        asset_symbol=row["asset_symbol"],
        balance=float(row["balance"]),
        protocol=row["protocol"],
        maturity_date=row["maturity_date"],
        is_active=row["is_active"],
        notes=row["notes"],
    )


def _as_decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


@router.get("/positions", response_model=list[DefiPositionResponse])
async def list_positions(
    user: AuthUser,
    db: Db,
    active: Annotated[bool | None, Query()] = None,
) -> list[DefiPositionResponse]:
    rows = await db.fetch(
        f"SELECT {_COLUMNS} FROM defi_positions "
        "WHERE user_id = $1 AND ($2::boolean IS NULL OR is_active = $2) "
        "ORDER BY maturity_date NULLS LAST, asset_symbol",
        uuid.UUID(user["id"]),
        active,
    )
    return [_to_response(r) for r in rows]


@router.post(
    "/positions", response_model=DefiPositionResponse, status_code=status.HTTP_201_CREATED
)
async def create_position(
    body: DefiPositionCreate, user: AuthUser, db: Db
) -> DefiPositionResponse:
    row = await db.fetchrow(
        "INSERT INTO defi_positions "
        "(user_id, protocol, asset_symbol, balance, maturity_date, is_active, notes) "
        f"VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING {_COLUMNS}",
        uuid.UUID(user["id"]),
        body.protocol,
        body.asset_symbol,
        _as_decimal(body.balance),
        body.maturity_date,
        body.is_active,
        body.notes,
    )
    return _to_response(row)


@router.put("/positions/{position_id}", response_model=DefiPositionResponse)
async def update_position(
    position_id: uuid.UUID, body: DefiPositionUpdate, user: AuthUser, db: Db
) -> DefiPositionResponse:
    row = await db.fetchrow(
        """
        UPDATE defi_positions SET
          protocol = COALESCE($3, protocol),
          asset_symbol = COALESCE($4, asset_symbol),
          balance = COALESCE($5, balance),
          maturity_date = COALESCE($6, maturity_date),
          is_active = COALESCE($7, is_active),
          notes = COALESCE($8, notes),
          updated_at = now()
        WHERE id = $1 AND user_id = $2
        """
        f" RETURNING {_COLUMNS}",
        position_id,
        uuid.UUID(user["id"]),
        body.protocol,
        body.asset_symbol,
        _as_decimal(body.balance),
        body.maturity_date,
        body.is_active,
        body.notes,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "posição DeFi não encontrada")
    return _to_response(row)


@router.delete("/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(position_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute(
        "DELETE FROM defi_positions WHERE id = $1 AND user_id = $2",
        position_id,
        uuid.UUID(user["id"]),
    )
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "posição DeFi não encontrada")


@router.get("/alerts", response_model=list[Alert])
async def defi_alerts(user: AuthUser, db: Db) -> list[Alert]:
    """Alertas de vencimento (30d/7d) das posições DeFi ativas — compute-on-read."""
    today = datetime.date.today()
    rows = await db.fetch(
        "SELECT asset_symbol, maturity_date, protocol FROM defi_positions "
        "WHERE user_id = $1 AND is_active AND maturity_date IS NOT NULL",
        uuid.UUID(user["id"]),
    )
    positions = [
        DefiMaturity(
            asset_symbol=r["asset_symbol"],
            maturity_date=r["maturity_date"],
            protocol=r["protocol"],
        )
        for r in rows
    ]
    return defi_maturity_alerts(positions, today)
