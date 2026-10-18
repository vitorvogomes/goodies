"""Contrato tipado dos endpoints /api/v1/market/* (§3.5: Pydantic na superfície nova)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PriceOut(BaseModel):
    """Preço corrente de um ticker + frescor (resultado da cadeia de fallback)."""

    ticker: str
    price_brl: float | None
    price_usd: float | None = None
    source: str | None = None
    is_manual: bool = False
    stale: bool
    last_updated: str | None = None  # ISO8601 ou None quando não há preço


class PricesResponse(BaseModel):
    """Lista de preços (ex.: todos os tickers da carteira)."""

    prices: list[PriceOut]


class SetPriceRequest(BaseModel):
    """Corpo do POST manual de preço (BRL)."""

    price_brl: Decimal = Field(ge=0)  # preço unitário: até 8 casas (asset_prices.price_brl)
    as_of: date | None = None  # Story 10.2: a data do preço informado (padrão: hoje)
