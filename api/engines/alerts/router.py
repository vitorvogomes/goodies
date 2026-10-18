"""Rotas da Central de avisos (AD-15): `GET /api/v1/alerts` e a dispensa."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import service
from .models import AlertList, DismissalIn

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=AlertList)
async def list_alerts(
    user: AuthUser,
    db: Db,
    periodo: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> AlertList:
    try:
        month = parse_periodo(periodo) if periodo else None
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None
    return await service.active_alerts(db, month)


@router.post("/dismissals", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(body: DismissalIn, user: AuthUser, db: Db) -> None:
    try:
        await service.dismiss(db, body.key, body.fingerprint)
    except service.NotDismissibleError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "aviso_nao_dispensavel", "message": "Esse aviso não pode ser dispensado."},
        ) from None
