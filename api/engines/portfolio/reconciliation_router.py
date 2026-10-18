"""Rotas da conciliação (Story 7.9 — AD-15). `/api/v1/wallets/reconciliation` mantém o caminho da
tela v1 (a conciliação carteira × operações passou para o portfolio, AD-1)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from engines.common.deps import AuthUser, Db
from engines.common.owner import get_owner_id

from . import reconciliation as service

router = APIRouter(tags=["portfolio:reconciliation"])


class ReconciliationOut(BaseModel):
    asset_symbol: str
    scanned_quantity: float
    registered_quantity: float
    delta: float
    value_brl: float | None = None
    value_usd: float | None = None


@router.get("/api/v1/portfolio/reconciliation", response_model=service.Reconciliation)
async def reconciliation(user: AuthUser, db: Db) -> service.Reconciliation:
    return await service.reconciliation(db, await get_owner_id(db))


@router.get("/api/v1/wallets/reconciliation", response_model=list[ReconciliationOut])
async def wallet_reconciliation_v1(user: AuthUser, db: Db) -> list[ReconciliationOut]:
    return [ReconciliationOut(**r) for r in await service.wallet_rows(db, user["id"])]
