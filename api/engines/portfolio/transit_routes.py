"""Endpoint da reconciliação de trânsito (Pilar 2): GET /api/v1/portfolio/transit."""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.portfolio.transit import calculate_transit

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio:transit"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class TransitRail(BaseModel):
    rail: str
    saiu_brl: float
    aplicado_brl: float
    em_transito_brl: float


class TransitCrypto(BaseModel):
    net_invested_brl: float
    current_value_brl: float
    resultado_brl: float


class TransitOut(BaseModel):
    rails: list[TransitRail]
    crypto: TransitCrypto


@router.get("/transit", response_model=TransitOut)
async def transit(user: AuthUser, db: Db) -> TransitOut:
    result = await calculate_transit(db, user["id"])
    return TransitOut(**result)
