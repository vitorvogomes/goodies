"""Endpoints de leitura do Wallet Engine — STORY-04-10/04-11.

`/api/v1/wallets/positions` (saldos escaneados valorados pelo preço m3) e
`/api/v1/wallets/reconciliation` (escaneado vs registrado em asset_operations). Só
leitura: a escrita é do worker `wallet_scan` (cron). Escopo por usuário.
"""
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.wallet import service

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
    value_brl: float | None
    stale: bool


class ReconciliationOut(BaseModel):
    asset_symbol: str
    scanned_quantity: float
    registered_quantity: float
    delta: float


@router.get("/positions", response_model=list[WalletPositionOut])
async def positions(user: AuthUser, db: Db) -> list[dict[str, object]]:
    return await service.list_wallet_positions(db, user["id"])


@router.get("/reconciliation", response_model=list[ReconciliationOut])
async def reconciliation(user: AuthUser, db: Db) -> list[dict[str, object]]:
    return await service.reconcile(db, user["id"])
