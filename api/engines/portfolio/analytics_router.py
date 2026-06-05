"""Portfolio analytics router — leitura de métricas (/api/v1/portfolio/*).

Endpoints de cálculo do Portfolio Engine (m2): XIRR, posições, alocação,
rebalanceamento, rendimentos, IR. Separado do router de CRUD (asset-operations).

Note: B008 (Depends in defaults) é padrão FastAPI e seguro aqui.
"""
from __future__ import annotations

# ruff: noqa: B008
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db

from . import service

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio:analytics"])


class SetPriceRequest(BaseModel):
    """Preço manual de um ticker (BRL)."""

    price_brl: float = Field(..., ge=0)


@router.put("/prices/{asset_symbol}")
async def set_manual_price(
    asset_symbol: str,
    body: SetPriceRequest,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Define/atualiza o preço manual de um ativo (upsert)."""
    return await service.upsert_price(db, asset_symbol, body.price_brl)


@router.get("/xirr")
async def get_portfolio_xirr(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """XIRR consolidado, por categoria e por ativo (taxa anualizada decimal)."""
    return await service.calculate_portfolio_xirr(db, user["id"])


@router.get("/positions")
async def get_positions(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Posições atuais por ativo, valoradas com preço manual."""
    return await service.calculate_positions(db, user["id"])
