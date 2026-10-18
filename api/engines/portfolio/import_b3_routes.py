"""Endpoint de import de relatórios B3 da página v1 (A4): consolidado, movimentação, negociação.

POST /api/v1/portfolio/import-b3?dry_run=<bool>&filename=<nome>
Corpo = bytes do .xlsx (octet-stream). Desde a Story 3.8 passa pelo protocolo `SourceAdapter`
(`B3Adapter`): prévia e, sem `dry_run`, confirmação. O tipo é detectado pela aba; a regra de
cobertura evita a dupla contagem trade-vs-liquidação; idempotente por hash. Arquivo inválido/vazio
-> 422 (nunca 5xx).
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.common.dates import today_brt
from engines.ingest import service as ingest_service

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
    filename: Annotated[str, Query()] = "",
) -> ImportB3Report:
    """Página v1 pelo protocolo da engine `ingest` (Story 3.8): `dry_run` = só a prévia."""
    data = await request.body()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "arquivo vazio")
    preview = await ingest_service.preview(db, [(filename or "relatorio-b3.xlsx", data)])
    plan = preview.files[0]
    if plan.error is not None or not (plan.source or "").startswith("b3_"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, plan.error or "não é um relatório da B3"
        )
    if "period" in plan.needs:
        # A página v1 não pede período: usa as datas das operações (ou hoje, no consolidado).
        start, end = plan.detail.get("date_range") or [today_brt().isoformat()] * 2
        preview = await ingest_service.replan(
            db, preview.batch_id, {plan.file_hash: {"period_start": start, "period_end": end}}
        )
        plan = preview.files[0]
    ftype = str(plan.source).removeprefix("b3_")
    prices = plan.detail.get("prices", {})
    report = ImportB3Report(
        file_type=ftype,
        parsed=int(plan.detail.get("parsed", 0)),
        imported=plan.new,
        skipped_duplicate=plan.existing,
        skipped_overlap=plan.skipped,
        overlap_tickers=plan.detail.get("overlap_tickers", []),
        new_tickers=plan.detail.get("new_tickers", []),
        date_range=plan.detail.get("date_range"),
        prices_upserted=len(prices),
        dry_run=dry_run,
        note="consolidado: posições e preços; ops vêm de movimentação/negociação"
        if ftype == "consolidado"
        else None,
    )
    if dry_run:
        return report
    try:
        result = await ingest_service.confirm(db, preview.batch_id, preview.hash)
    except ingest_service.BatchError as exc:
        raise HTTPException(exc.status, exc.message) from None
    detail = result.applied[0] if result.applied else {}
    upserted = int(detail.get("prices_upserted", len(prices)))
    return report.model_copy(
        update={
            "imported": result.imported if ftype != "consolidado" else plan.new,
            "prices_upserted": upserted,
            "prices_skipped_manual": len(prices) - upserted,
        }
    )
