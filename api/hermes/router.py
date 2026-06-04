"""Endpoints Hermes (STORY-01-09): registro rápido de despesa/receita.

Auth via service token scope=hermes (secret próprio — ADR-006/007), distinto do
JWT de usuário. O request traz amount como magnitude positiva; o endpoint aplica
o sinal (despesa = negativa, receita = positiva) ao gravar em transactions.
Hermes é opcional — o Goodies funciona 100% sem ele.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, Field

from auth.security import decode_hermes_token
from db.connection import get_db

router = APIRouter(prefix="/api/v1/hermes", tags=["hermes"])

_bearer = HTTPBearer(auto_error=False)


async def get_hermes_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token ausente")
    try:
        payload = decode_hermes_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido ou expirado") from None
    if payload.get("scope") != "hermes":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "escopo inválido")
    return str(payload.get("sub", "hermes"))


Hermes = Annotated[str, Depends(get_hermes_principal)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class HermesEntry(BaseModel):
    account_id: uuid.UUID
    date: datetime.date
    amount: float = Field(gt=0)  # magnitude positiva; sinal aplicado pelo endpoint
    category: str = Field(min_length=1)
    description: str | None = None


class HermesResult(BaseModel):
    id: str
    date: str
    amount: float  # já com o sinal aplicado
    category: str


async def _insert(
    db: asyncpg.Connection, body: HermesEntry, signed_amount: float
) -> HermesResult:
    try:
        row = await db.fetchrow(
            "INSERT INTO transactions (account_id, date, amount, category, description) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id, date, amount, category",
            body.account_id,
            body.date,
            Decimal(str(signed_amount)),
            body.category,
            body.description,
        )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conta inexistente") from None
    return HermesResult(
        id=str(row["id"]),
        date=row["date"].isoformat(),
        amount=float(row["amount"]),
        category=row["category"],
    )


@router.post("/expenses", response_model=HermesResult, status_code=status.HTTP_201_CREATED)
async def register_expense(body: HermesEntry, principal: Hermes, db: Db) -> HermesResult:
    return await _insert(db, body, -body.amount)


@router.post("/income", response_model=HermesResult, status_code=status.HTTP_201_CREATED)
async def register_income(body: HermesEntry, principal: Hermes, db: Db) -> HermesResult:
    return await _insert(db, body, body.amount)
