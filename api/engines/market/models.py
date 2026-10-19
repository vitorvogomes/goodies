"""Contrato tipado dos endpoints /api/v1/market/* (§3.5: Pydantic na superfície nova)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


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
    """Corpo do POST manual de preço: em R$ ou, no token cripto, em US$ (o R$ sai
    da cotação do dólar e é refeito quando ela muda)."""

    price_brl: Decimal | None = Field(default=None, ge=0)  # unitário, até 8 casas
    price_usd: Decimal | None = Field(default=None, ge=0)
    as_of: date | None = None  # Story 10.2: a data do preço informado (padrão: hoje)

    @model_validator(mode="after")
    def _one_currency(self) -> SetPriceRequest:
        if (self.price_brl is None) == (self.price_usd is None):
            raise ValueError("Informe o preço em R$ ou em US$.")
        return self
