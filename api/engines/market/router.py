"""Market Engine router — /api/v1/market/* (STORY-03-08/09).

Leitura de preço (via cadeia de fallback `service.get_price`) + escrita manual
(delega ao chokepoint `portfolio.service.upsert_price`, is_manual=True). Contrato
tipado em Pydantic (`models.py`). Migração total do antigo `PUT /portfolio/prices`
para cá (decisão do m3).
"""
from __future__ import annotations

# ruff: noqa: B008
import asyncpg
from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.market import service
from engines.market.models import PriceOut, PricesResponse, SetPriceRequest
from engines.portfolio import service as portfolio_service

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/prices", response_model=PricesResponse)
async def list_prices(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> PricesResponse:
    """Preço corrente (com flag de staleness) de todos os tickers da carteira."""
    prices = await service.list_user_prices(db, user["id"])
    return PricesResponse(prices=[PriceOut(**p) for p in prices])


@router.get("/prices/{ticker}", response_model=PriceOut)
async def get_price(
    ticker: str,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> PriceOut:
    """Preço corrente de um ticker (Redis → Postgres → null/stale)."""
    category = await db.fetchval(
        "SELECT asset_category FROM asset_operations "
        "WHERE user_id = $1 AND asset_symbol = $2 LIMIT 1",
        user["id"],
        ticker,
    )
    return PriceOut(**await service.get_price(db, ticker, category=category))


@router.post("/prices/{ticker}", response_model=PriceOut)
async def set_manual_price(
    ticker: str,
    body: SetPriceRequest,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> PriceOut:
    """Define/atualiza o preço manual de um ticker (is_manual=True; sempre vence)."""
    await portfolio_service.upsert_price(db, ticker, body.price_brl)
    # Invalida o cache Redis para o override manual não ficar mascarado por um preço
    # de mercado cacheado (manual sempre vence; ver invalidate_price_cache).
    await service.invalidate_price_cache(ticker)
    return PriceOut(**await service.get_price(db, ticker))
