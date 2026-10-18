"""Renda fixa pelo CDI: %CDI e saldo informado de cada ativo (pendência P28)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from engines.common.deps import AuthUser, Db

from . import rf_anchors
from .rf_anchors import AnchorIn, RfRow

router = APIRouter(prefix="/api/v1/portfolio/renda-fixa", tags=["portfolio:renda-fixa"])


@router.get("", response_model=list[RfRow])
async def list_rf(user: AuthUser, db: Db) -> list[RfRow]:
    return await rf_anchors.list_rf(db)


@router.put("/{ticker}", response_model=RfRow)
async def save_anchor(ticker: str, body: AnchorIn, user: AuthUser, db: Db) -> RfRow:
    try:
        return await rf_anchors.save_anchor(db, ticker, body)
    except rf_anchors.FutureAnchorError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"error": "data_futura", "message": str(exc)}
        ) from None
    except LookupError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "ativo_inexistente", "message": f"{ticker} não é valorado pelo CDI."},
        ) from None
