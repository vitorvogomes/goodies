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
from engines.ledger.importer import import_statement, parse_account_number, parse_statement

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


async def _resolve_account(
    db: asyncpg.Connection, acctid: str | None, account_id: uuid.UUID | None
) -> uuid.UUID:
    """Roteia o import: OFX → conta pelo ACCTID; CSV/sem ACCTID → account_id explícito."""
    if acctid:
        row = await db.fetchrow("SELECT id FROM accounts WHERE account_number = $1", acctid)
        if row is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"conta com número {acctid} não cadastrada; crie-a antes de importar",
            )
        resolved: uuid.UUID = row["id"]
        if account_id is not None and account_id != resolved:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "conta selecionada difere da conta do arquivo"
            )
        return resolved
    if account_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "informe a conta para arquivos sem número de conta (CSV)",
        )
    if not await db.fetchval("SELECT 1 FROM accounts WHERE id = $1", account_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conta não encontrada")
    return account_id


@router.post("/import", response_model=ImportReport)
async def import_endpoint(
    request: Request,
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    filename: Annotated[str, Query()] = "",
) -> ImportReport:
    content = (await request.body()).decode("utf-8", errors="replace")
    target = await _resolve_account(db, parse_account_number(content), account_id)

    entries = parse_statement(filename, content)
    if not entries:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "nenhuma transação reconhecida no arquivo"
        )

    report = await import_statement(db, target, entries, _self_identifiers())
    return ImportReport(
        parsed=len(entries),
        imported=report.imported,
        duplicates=report.duplicates,
        skipped=report.skipped,
        errors=report.errors,
    )
