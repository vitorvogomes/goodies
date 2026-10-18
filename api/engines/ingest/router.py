"""Rotas da engine ingest (AD-15): prévia (multiarquivo), nova prévia com escolhas e confirmação."""

from __future__ import annotations

import json
from typing import Annotated

import asyncpg
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from engines.common.dates import today_brt
from engines.common.deps import AuthUser, Db
from engines.common.models import Uuid

from . import service
from .models import (
    ConfirmIn,
    ConfirmOut,
    ImportHistory,
    PreviewOut,
    ReplanIn,
    SourceRow,
    UndoPreview,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

_BAD_OVERRIDES = {"error": "escolhas_invalidas", "message": "Escolhas da prévia inválidas."}


def _http(exc: service.BatchError) -> HTTPException:
    return HTTPException(exc.status, {"error": exc.code, "message": exc.message})


@router.post("/preview", response_model=PreviewOut)
async def preview(
    user: AuthUser,
    db: Db,
    files: Annotated[list[UploadFile], File()],
    overrides: Annotated[str | None, Form()] = None,
) -> PreviewOut:
    try:
        chosen = json.loads(overrides) if overrides else {}
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_OVERRIDES) from None
    if not isinstance(chosen, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_OVERRIDES)
    contents = [(f.filename or "arquivo", await f.read()) for f in files]
    return await service.preview(db, contents, chosen)


@router.get("/sources", response_model=list[SourceRow])
async def list_sources(user: AuthUser, db: Db) -> list[SourceRow]:
    return await service.sources(db, today_brt())


@router.post("/replan", response_model=PreviewOut)
async def replan(body: ReplanIn, user: AuthUser, db: Db) -> PreviewOut:
    try:
        return await service.replan(db, body.batch_id, body.overrides)
    except service.BatchError as exc:
        raise _http(exc) from None


@router.get("/batches", response_model=ImportHistory)
async def list_history(user: AuthUser, db: Db) -> ImportHistory:
    return await service.history(db)


@router.post("/batches/{batch_id}/undo/preview", response_model=UndoPreview)
async def undo_preview(batch_id: Uuid, user: AuthUser, db: Db) -> UndoPreview:
    try:
        return await service.undo_preview(db, batch_id)
    except service.BatchError as exc:
        raise _http(exc) from None


@router.post("/batches/{batch_id}/undo", response_model=UndoPreview)
async def undo(batch_id: Uuid, user: AuthUser, db: Db) -> UndoPreview:
    try:
        return await service.undo(db, batch_id)
    except service.BatchError as exc:
        raise _http(exc) from None
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "lote_com_curadoria",
                "message": "O lote tem uma operação protegida (curadoria) e não pode ser desfeito.",
            },
        ) from None


@router.post("/confirm", response_model=ConfirmOut)
async def confirm(body: ConfirmIn, user: AuthUser, db: Db) -> ConfirmOut:
    try:
        return await service.confirm(db, body.batch_id, body.hash)
    except service.BatchError as exc:
        raise _http(exc) from None
