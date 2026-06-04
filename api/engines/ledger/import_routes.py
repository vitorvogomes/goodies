"""Endpoint de import de extrato Nubank (STORY-01-13-14).

POST /api/v1/ledger/import?account_id=<uuid>&filename=<nome>
Corpo = conteúdo do arquivo (OFX ou CSV). Upload por corpo cru (sem
python-multipart). Idempotente (dedup por external_id). Protegido por JWT.
"""

import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from auth.dependencies import get_current_user
from config import settings
from db.connection import get_db
from engines.ledger.importer import import_statement, parse_statement

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger:import"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class ImportReport(BaseModel):
    parsed: int
    imported: int
    duplicates: int
    skipped: int
    errors: int


def _self_identifiers() -> list[str]:
    return [s.strip() for s in settings.ledger_self_identifiers.split(",") if s.strip()]


@router.post("/import", response_model=ImportReport)
async def import_endpoint(
    request: Request,
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID, Query()],
    filename: Annotated[str, Query()] = "",
) -> ImportReport:
    exists = await db.fetchval("SELECT 1 FROM accounts WHERE id = $1", account_id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")

    content = (await request.body()).decode("utf-8", errors="replace")
    entries = parse_statement(filename, content)
    if not entries:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "nenhuma transação reconhecida no arquivo"
        )

    report = await import_statement(db, account_id, entries, _self_identifiers())
    return ImportReport(
        parsed=len(entries),
        imported=report.imported,
        duplicates=report.duplicates,
        skipped=report.skipped,
        errors=report.errors,
    )
