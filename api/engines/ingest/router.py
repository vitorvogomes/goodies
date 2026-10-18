"""Rotas da engine ingest (AD-15): prévia (multiarquivo), nova prévia com escolhas e confirmação."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from engines.common.deps import AuthUser, Db

from . import service
from .models import ConfirmIn, ConfirmOut, PreviewOut, ReplanIn

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


@router.post("/replan", response_model=PreviewOut)
async def replan(body: ReplanIn, user: AuthUser, db: Db) -> PreviewOut:
    try:
        return await service.replan(db, body.batch_id, body.overrides)
    except service.BatchError as exc:
        raise _http(exc) from None


@router.post("/confirm", response_model=ConfirmOut)
async def confirm(body: ConfirmIn, user: AuthUser, db: Db) -> ConfirmOut:
    try:
        return await service.confirm(db, body.batch_id, body.hash)
    except service.BatchError as exc:
        raise _http(exc) from None
