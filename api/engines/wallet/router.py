"""Endpoints de leitura do Wallet Engine — STORY-04-10/04-11.

`/api/v1/wallets/positions` (saldos escaneados valorados pelo preço m3) e
`/api/v1/wallets/reconciliation` (escaneado vs registrado em asset_operations). Só
leitura: a escrita é do worker `wallet_scan` (cron). Escopo por usuário.
"""
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.portfolio.service import invalidate_xirr_cache
from engines.wallet import service
from engines.wallet.service import ManualPositionConflict

router = APIRouter(prefix="/api/v1/wallets", tags=["wallet"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class WalletPositionOut(BaseModel):
    chain: str
    wallet_address: str
    asset_symbol: str
    quantity: float
    source: str
    scanned_at: str
    price_brl: float | None
    price_usd: float | None
    value_brl: float | None
    value_usd: float | None
    stale: bool
    is_manual: bool


class ManualPositionIn(BaseModel):
    chain: str = Field(min_length=1)
    asset_symbol: str = Field(min_length=1)
    quantity: float = Field(ge=0)

    @field_validator("chain", "asset_symbol")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("não pode ser vazio")
        return v


class ManualPositionOut(BaseModel):
    chain: str
    asset_symbol: str
    quantity: float


class ReconciliationOut(BaseModel):
    asset_symbol: str
    scanned_quantity: float
    registered_quantity: float
    delta: float
    value_brl: float | None = None
    value_usd: float | None = None


@router.get("/positions", response_model=list[WalletPositionOut])
async def positions(user: AuthUser, db: Db) -> list[dict[str, object]]:
    return await service.list_wallet_positions(db, user["id"])


@router.post("/positions/manual", response_model=ManualPositionOut)
async def create_manual_position(
    body: ManualPositionIn, user: AuthUser, db: Db
) -> ManualPositionOut:
    """Entrada manual (ex.: Liquid confidencial). Upsert por (chain, asset_symbol)."""
    try:
        await service.upsert_manual_wallet_position(
            db, user["id"], body.chain, body.asset_symbol, body.quantity
        )
    except ManualPositionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    # a posição manual alimenta o XIRR consolidado/Cripto via sleeve (m4): invalida o
    # cache (1h) p/ o dashboard não ficar incoerente após a edição. Achado C7.
    await invalidate_xirr_cache(user["id"])
    return ManualPositionOut(
        chain=body.chain, asset_symbol=body.asset_symbol, quantity=body.quantity
    )


@router.delete(
    "/positions/manual/{chain}/{asset_symbol}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_manual_position(
    chain: str, asset_symbol: str, user: AuthUser, db: Db
) -> None:
    removed = await service.delete_manual_wallet_position(
        db, user["id"], chain, asset_symbol
    )
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "posição manual não encontrada")
    await invalidate_xirr_cache(user["id"])  # sleeve mudou → XIRR stale (C7)


@router.get("/reconciliation", response_model=list[ReconciliationOut])
async def reconciliation(user: AuthUser, db: Db) -> list[dict[str, object]]:
    return await service.reconcile(db, user["id"])
