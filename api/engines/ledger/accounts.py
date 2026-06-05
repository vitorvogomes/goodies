"""CRUD de contas (STORY-01-02 + adendo multi-conta).

Sem ORM: SQL explícito via asyncpg (conventions.md). Rotas protegidas por
get_current_user. accounts referenciada por transactions.account_id — DELETE de
conta com transações retorna 409. `account_number` (ex.: ACCTID do OFX) é único
quando presente — roteia o import e detecta transferência interna.
"""

import uuid
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api/v1/accounts", tags=["ledger:accounts"])

AccountType = Literal["bank", "broker", "crypto", "manual"]

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]

_COLUMNS = "id, name, type, currency, account_number"


class AccountCreate(BaseModel):
    name: str = Field(min_length=1)
    type: AccountType
    currency: str = "BRL"
    account_number: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    type: AccountType | None = None
    currency: str | None = None
    account_number: str | None = None


class AccountResponse(BaseModel):
    id: str
    name: str
    type: str
    currency: str
    account_number: str | None


def _to_response(row: asyncpg.Record) -> AccountResponse:
    return AccountResponse(
        id=str(row["id"]),
        name=row["name"],
        type=row["type"],
        currency=row["currency"],
        account_number=row["account_number"],
    )


@router.get("", response_model=list[AccountResponse])
async def list_accounts(user: AuthUser, db: Db) -> list[AccountResponse]:
    rows = await db.fetch(f"SELECT {_COLUMNS} FROM accounts ORDER BY created_at")
    return [_to_response(r) for r in rows]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, user: AuthUser, db: Db) -> AccountResponse:
    try:
        row = await db.fetchrow(
            "INSERT INTO accounts (name, type, currency, account_number) "
            f"VALUES ($1, $2, $3, $4) RETURNING {_COLUMNS}",
            body.name,
            body.type,
            body.currency,
            body.account_number,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "número de conta já cadastrado") from None
    return _to_response(row)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID, body: AccountUpdate, user: AuthUser, db: Db
) -> AccountResponse:
    try:
        row = await db.fetchrow(
            """
            UPDATE accounts SET
              name = COALESCE($2, name),
              type = COALESCE($3, type),
              currency = COALESCE($4, currency),
              account_number = COALESCE($5, account_number)
            WHERE id = $1
            """
            f" RETURNING {_COLUMNS}",
            account_id,
            body.name,
            body.type,
            body.currency,
            body.account_number,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "número de conta já cadastrado") from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return _to_response(row)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    try:
        result = await db.execute("DELETE FROM accounts WHERE id = $1", account_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "conta possui transações; remova-as antes"
        ) from None
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
