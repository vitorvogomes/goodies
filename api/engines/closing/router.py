"""Rotas da engine closing (AD-15)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import MIN_MONTH, parse_periodo, today_brt
from engines.common.deps import AuthUser, Db

from . import service
from .checks import run_checks
from .models import (
    Checklist,
    CloseCheck,
    CloseIn,
    CloseOut,
    MonthState,
    MonthSummary,
    ReopenOut,
    ReopenPreview,
)

router = APIRouter(prefix="/api/v1/closing", tags=["closing"])

_BAD_MONTH = {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."}


@router.get("/months/{mes}/summary", response_model=MonthSummary)
async def month_summary(mes: str, user: AuthUser, db: Db) -> MonthSummary:
    try:
        month = parse_periodo(mes)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_MONTH) from None
    return await service.month_summary(db, month)


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
        raise _conflict(exc) from None


@router.get("/months", response_model=list[MonthState])
async def list_months(
    user: AuthUser, db: Db, de: str | None = None, ate: str | None = None
) -> list[MonthState]:
    start = _month(de) if de else MIN_MONTH
    end = _month(ate) if ate else today_brt().replace(day=1)
    return await service.month_states(db, start, end)


@router.get("/months/{mes}/checklist", response_model=Checklist)
async def month_checklist(mes: str, user: AuthUser, db: Db) -> Checklist:
    return await service.checklist(db, _month(mes))


def _conflict(exc: service.CloseError) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "error": exc.code,
            "message": exc.message,
            "checks": [c.model_dump() for c in exc.checks],
        },
    )


@router.get("/months/{mes}/reopen/preview", response_model=ReopenPreview)
async def reopen_preview(mes: str, user: AuthUser, db: Db) -> ReopenPreview:
    try:
        return await service.reopen_preview(db, _month(mes))
    except service.CloseError as exc:
        raise _conflict(exc) from None


@router.post("/months/{mes}/reopen", response_model=ReopenOut)
async def reopen_month(mes: str, user: AuthUser, db: Db) -> ReopenOut:
    try:
        return await service.reopen_month(db, _month(mes))
    except service.CloseError as exc:
        raise _conflict(exc) from None
