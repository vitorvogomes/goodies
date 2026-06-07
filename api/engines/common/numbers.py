"""Helpers numéricos compartilhados entre engines."""
from __future__ import annotations

from decimal import Decimal


def as_decimal(value: float | None) -> Decimal | None:
    """float → Decimal via str (evita ruído binário do float); None → None.

    Usado nas escritas em colunas NUMERIC (ledger, DeFi) — o str() garante o
    arredondamento correto que o NUMERIC(p,s) aplica.
    """
    return Decimal(str(value)) if value is not None else None


def value_of(quantity: float, price: float | None) -> float | None:
    """quantidade x preço; None quando não há preço (ativo sem fonte)."""
    return quantity * price if price is not None else None
