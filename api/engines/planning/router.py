"""Rotas da engine planning (AD-15): o plano do mês. O orçamento é lido por `closing` (AD-8)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import service
from .models import DividasIn, MonthPlanOut

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])


@router.put("/months/{mes}/dividas", response_model=MonthPlanOut)
async def set_dividas(mes: str, body: DividasIn, user: AuthUser, db: Db) -> MonthPlanOut:
    try:
        month = parse_periodo(mes)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None
    try:
        return await service.set_dividas(db, month, body.valor)
    except service.MonthClosedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "mes_fechado", "message": "Mês fechado: reabra para mudar as dívidas."},
        ) from None
