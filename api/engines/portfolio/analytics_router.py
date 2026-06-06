"""Portfolio analytics router — leitura de métricas (/api/v1/portfolio/*).

Endpoints de cálculo do Portfolio Engine (m2): XIRR, posições, alocação,
rebalanceamento, rendimentos, IR. Separado do router de CRUD (asset-operations).

Note: B008 (Depends in defaults) é padrão FastAPI e seguro aqui.
"""
from __future__ import annotations

# ruff: noqa: B008
from datetime import date
from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, Query
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
    """Define/atualiza o preço manual de um ativo (upsert).

    A invalidação do cache de XIRR (ADR-008) agora é feita dentro de `upsert_price`
    (chokepoint §3.4), cobrindo também o worker do Market Engine.
    """
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


@router.get("/allocation")
async def get_allocation(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Alocação atual vs meta por categoria + desvio em pontos percentuais."""
    return await service.calculate_allocation(db, user["id"])


@router.get("/rebalancing")
async def get_rebalancing(
    amount: float = Query(..., ge=0),
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Sugestão de aporte (nunca vende): distribui `amount` por desvio negativo."""
    return await service.calculate_rebalancing(db, user["id"], amount)


@router.get("/income")
async def get_income(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    """Rendimentos (dividendo/juros) por ativo/categoria, separados do capital."""
    return await service.calculate_income(db, user["id"], date_from, date_to)


@router.get("/ir-estimate")
async def get_ir_estimate(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Estimativa de IR por categoria de renda variável (ganho x alíquota)."""
    return await service.estimate_ir(db, user["id"])


@router.get("/ir-crypto")
async def get_ir_crypto(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Consolidação mensal de vendas de cripto + alerta de 80% do limite."""
    return await service.calculate_crypto_ir_monthly(db, user["id"])
