"""CRUD de posições DeFi (entrada manual, ADR-004) — STORY-04-08.

Posições DeFi (Phantom) que não vêm de scan on-chain (xSOL/hyUSD com vencimento).
`/api/v1/defi/positions` (POST/GET/PUT/DELETE), escopo por usuário. Os alertas de
vencimento (04-09) leem desta tabela.
"""
import datetime
import uuid
from collections.abc import Callable
from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.common.dates import today_brt
from engines.common.numbers import as_decimal, value_of
from engines.ledger.service import Alert
from engines.portfolio.service import invalidate_xirr_cache
from engines.wallet.defi import DefiMaturity, defi_maturity_alerts
from engines.wallet.service import prices_by_ticker

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

    @model_validator(mode="after")
    def _no_null_on_required(self) -> "DefiPositionUpdate":
        # PUT parcial: ausente = não altera; null explícito só vale p/ colunas nullable
        # (protocol/maturity_date/notes). Nas NOT NULL viraria NotNullViolation → 500.
        nulled = [
            f
            for f in ("asset_symbol", "balance", "is_active")
            if f in self.model_fields_set and getattr(self, f) is None
        ]
        if nulled:
            raise ValueError(f"campos não aceitam null: {', '.join(nulled)}")
        return self


class DefiPositionResponse(BaseModel):
    id: str
    asset_symbol: str
    balance: float
    protocol: str | None
    maturity_date: datetime.date | None
    is_active: bool
    notes: str | None
    # Valoração (m4): preço m3 (asset_prices) via alias CoinGecko. None sem fonte (ex.: YT-xSOL).
    price_brl: float | None = None
    price_usd: float | None = None
    value_brl: float | None = None
    value_usd: float | None = None


def _to_response(
    row: asyncpg.Record,
    prices: dict[str, tuple[float | None, float | None]] | None = None,
) -> DefiPositionResponse:
    balance = float(row["balance"])
    brl, usd = (prices or {}).get(row["asset_symbol"], (None, None))
    return DefiPositionResponse(
        id=str(row["id"]),
        asset_symbol=row["asset_symbol"],
        balance=balance,
        protocol=row["protocol"],
        maturity_date=row["maturity_date"],
        is_active=row["is_active"],
        notes=row["notes"],
        price_brl=brl,
        price_usd=usd,
        value_brl=value_of(balance, brl),
        value_usd=value_of(balance, usd),
    )


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
    prices = await prices_by_ticker(db, [r["asset_symbol"] for r in rows])
    return [_to_response(r, prices) for r in rows]


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
        as_decimal(body.balance),
        body.maturity_date,
        body.is_active,
        body.notes,
    )
    # posição DeFi entra no valor do sleeve → XIRR consolidado/Cripto stale (C7)
    await invalidate_xirr_cache(user["id"])
    return _to_response(row, await prices_by_ticker(db, [row["asset_symbol"]]))


# colunas atualizáveis via PUT → (nome no schema, como extrair o valor do body)
_UPDATABLE: dict[str, Callable[[DefiPositionUpdate], Any]] = {
    "protocol": lambda b: b.protocol,
    "asset_symbol": lambda b: b.asset_symbol,
    "balance": lambda b: as_decimal(b.balance),
    "maturity_date": lambda b: b.maturity_date,
    "is_active": lambda b: b.is_active,
    "notes": lambda b: b.notes,
}


@router.put("/positions/{position_id}", response_model=DefiPositionResponse)
async def update_position(
    position_id: uuid.UUID, body: DefiPositionUpdate, user: AuthUser, db: Db
) -> DefiPositionResponse:
    # SET dinâmico só com os campos ENVIADOS (model_fields_set): assim maturity_date=null
    # de fato limpa o vencimento, em vez de o COALESCE manter a data antiga (alerta fantasma).
    uid = uuid.UUID(user["id"])
    sets: list[str] = []
    values: list[Any] = []
    for col, extract in _UPDATABLE.items():
        if col in body.model_fields_set:
            values.append(extract(body))
            sets.append(f"{col} = ${len(values) + 2}")  # $1=id, $2=user_id
    if sets:
        sets.append("updated_at = now()")
        row = await db.fetchrow(
            f"UPDATE defi_positions SET {', '.join(sets)} "
            f"WHERE id = $1 AND user_id = $2 RETURNING {_COLUMNS}",
            position_id,
            uid,
            *values,
        )
    else:  # body vazio → devolve a posição atual sem tocar
        row = await db.fetchrow(
            f"SELECT {_COLUMNS} FROM defi_positions WHERE id = $1 AND user_id = $2",
            position_id,
            uid,
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "posição DeFi não encontrada")
    if sets:  # só invalida quando houve mudança de fato (body vazio = no-op)
        await invalidate_xirr_cache(user["id"])  # sleeve mudou → XIRR stale (C7)
    return _to_response(row, await prices_by_ticker(db, [row["asset_symbol"]]))


@router.delete("/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(position_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute(
        "DELETE FROM defi_positions WHERE id = $1 AND user_id = $2",
        position_id,
        uuid.UUID(user["id"]),
    )
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "posição DeFi não encontrada")
    await invalidate_xirr_cache(user["id"])  # sleeve mudou → XIRR stale (C7)


@router.get("/alerts", response_model=list[Alert])
async def defi_alerts(user: AuthUser, db: Db) -> list[Alert]:
    """Alertas de vencimento (30d/7d) das posições DeFi ativas — compute-on-read."""
    today = today_brt()  # fuso BRT — em prod UTC daria off-by-one nas bordas (débito m4)
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
