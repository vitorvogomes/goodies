"""Endpoint de import de extrato Nubank da página v1 (STORY-01-13-14).

POST /api/v1/ledger/import?account_id=<uuid>&filename=<nome>
Corpo = conteúdo do arquivo (OFX ou CSV). Desde a Story 3.3 passa pelo protocolo `SourceAdapter`
(prévia + confirmação de uma vez); o Hub de import usa `/api/v1/ingest/*`.
"""

import hashlib
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.ingest import service as ingest_service
from engines.ledger.importer import parse_account_number

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger:import"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class ImportReport(BaseModel):
    parsed: int
    imported: int
    duplicates: int
    skipped: int
    errors: int
    by_kind: dict[str, int] = {}  # novas por kind (income/expense/investment/transfer)


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
    """Página v1: prévia e confirmação de uma vez, pelo protocolo da engine `ingest` (Story 3.3)."""
    raw = await request.body()
    content = raw.decode("utf-8", errors="replace")
    target = await _resolve_account(db, parse_account_number(content), account_id)
    name = filename or ("extrato.ofx" if parse_account_number(content) else "extrato.csv")
    digest = hashlib.sha256(raw).hexdigest()
    preview = await ingest_service.preview(
        db, [(name, raw)], {digest: {"account_id": str(target)}}
    )
    plan = preview.files[0]
    if plan.error is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, plan.error)
    try:
        result = await ingest_service.confirm(db, preview.batch_id, preview.hash)
    except ingest_service.BatchError as exc:
        raise HTTPException(exc.status, exc.message) from None
    detail = result.applied[0] if result.applied else {}
    return ImportReport(
        parsed=plan.new + plan.existing,
        imported=result.imported,
        duplicates=plan.existing,
        skipped=plan.skipped,
        errors=int(detail.get("errors", 0)),
        by_kind=dict(detail.get("by_kind", {})),
    )
