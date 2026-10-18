"""Rotas da engine closing (AD-15)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import service
from .models import MonthSummary

router = APIRouter(prefix="/api/v1/closing", tags=["closing"])

_BAD_MONTH = {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."}


@router.get("/months/{mes}/summary", response_model=MonthSummary)
async def month_summary(mes: str, user: AuthUser, db: Db) -> MonthSummary:
    try:
        month = parse_periodo(mes)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_MONTH) from None
    return await service.build_month_summary(db, month)
