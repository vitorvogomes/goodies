"""Endpoint de import de relatórios B3 (A4): consolidado, movimentação, negociação.

POST /api/v1/portfolio/import-b3?dry_run=<bool>
Corpo = bytes do .xlsx (Content-Type application/octet-stream; sem multipart, como
o import do ledger usa corpo cru). O tipo é detectado pela aba; a regra de cobertura
(no serviço) evita a dupla contagem trade-vs-liquidação. Idempotente (dedup por
external_id). Protegido por JWT. Arquivo inválido/vazio -> 422 (nunca 5xx).
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.portfolio.b3_import_service import import_b3_workbook
from engines.portfolio.b3_workbook import load_workbook_sheets

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio:import-b3"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class ImportB3Report(BaseModel):
    file_type: str
    parsed: int
    imported: int
    skipped_duplicate: int
    skipped_overlap: int
    overlap_tickers: list[str]
    new_tickers: list[str]
    date_range: list[str] | None
    prices_upserted: int
    prices_skipped_manual: int = 0
    dry_run: bool
    note: str | None = None


@router.post("/import-b3", response_model=ImportB3Report)
async def import_b3_endpoint(
    request: Request,
    user: AuthUser,
    db: Db,
    dry_run: Annotated[bool, Query()] = False,
) -> ImportB3Report:
    data = await request.body()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "arquivo vazio")
    try:
        sheets = load_workbook_sheets(data)
        report = await import_b3_workbook(db, user["id"], sheets, dry_run=dry_run)
    except ValueError as exc:  # bytes inválidos ou tipo de arquivo não reconhecido
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
        ) from exc
    return ImportB3Report(**report)
