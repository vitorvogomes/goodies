"""Rotas do Painel principal (AD-15)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import service
from .models import Painel

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])


@router.get("/painel", response_model=Painel)
async def painel(
    user: AuthUser, db: Db, periodo: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]
) -> Painel:
    try:
        month = parse_periodo(periodo)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None
    return await service.painel(db, month)
