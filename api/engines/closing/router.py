"""Rotas da engine closing (AD-15)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import service
from .checks import run_checks
from .models import CloseCheck, CloseIn, CloseOut, MonthSummary

router = APIRouter(prefix="/api/v1/closing", tags=["closing"])

_BAD_MONTH = {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."}


@router.get("/months/{mes}/summary", response_model=MonthSummary)
async def month_summary(mes: str, user: AuthUser, db: Db) -> MonthSummary:
    try:
        month = parse_periodo(mes)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_MONTH) from None
    return await service.build_month_summary(db, month)


def _month(mes: str) -> date:
    try:
        return parse_periodo(mes)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_MONTH) from None


@router.get("/months/{mes}/checks", response_model=list[CloseCheck])
async def close_checks(mes: str, user: AuthUser, db: Db) -> list[CloseCheck]:
    return await run_checks(db, _month(mes))


@router.post("/months/{mes}/close", response_model=CloseOut, status_code=status.HTTP_201_CREATED)
async def close_month(mes: str, body: CloseIn, user: AuthUser, db: Db) -> CloseOut:
    try:
        return await service.close_month(db, _month(mes), body.confirmar)
    except service.CloseError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": exc.code,
                "message": exc.message,
                "checks": [c.model_dump() for c in exc.checks],
            },
        ) from None
