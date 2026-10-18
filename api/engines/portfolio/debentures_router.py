"""Rotas das debêntures (Story 7.6 — AD-15): o cadastro (Ajustes › Debêntures) e a dispensa do
aporte sugerido na Revisão."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from engines.common.deps import AuthUser, Db
from engines.common.models import Uuid

from . import debentures as service
from .debentures import (
    ContributionIn,
    ContributionPatch,
    ContributionRow,
    DebentureIn,
    DebenturePatch,
    DebentureRow,
)

router = APIRouter(prefix="/api/v1/portfolio/debentures", tags=["portfolio:debentures"])

_NOT_FOUND = {"error": "debenture_nao_encontrada", "message": "Debênture não encontrada."}
_NO_CONTRIBUTION = {
    "error": "integralizacao_nao_encontrada",
    "message": "Integralização não encontrada.",
}
_FUTURE = {"error": "data_futura", "message": "A data não pode ser depois de hoje."}


@router.get("", response_model=list[DebentureRow])
async def list_debentures(user: AuthUser, db: Db) -> list[DebentureRow]:
    return await service.list_debentures(db)


@router.post("", response_model=DebentureRow, status_code=status.HTTP_201_CREATED)
async def create_debenture(body: DebentureIn, user: AuthUser, db: Db) -> DebentureRow:
    return await service.create_debenture(db, body)


@router.patch("/{debenture_id}", response_model=DebentureRow)
async def update_debenture(
    debenture_id: Uuid, body: DebenturePatch, user: AuthUser, db: Db
) -> DebentureRow:
    try:
        return await service.update_debenture(db, str(debenture_id), body)
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None


@router.post("/contributions/{contribution_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_contribution(contribution_id: Uuid, user: AuthUser, db: Db) -> None:
    try:
        await service.dismiss_contribution(db, str(contribution_id))
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None


# ---- Integralizações (P17) ----


@router.get("/{debenture_id}/contributions", response_model=list[ContributionRow])
async def list_contributions(debenture_id: Uuid, user: AuthUser, db: Db) -> list[ContributionRow]:
    try:
        return await service.list_contributions(db, str(debenture_id))
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None


@router.post(
    "/{debenture_id}/contributions",
    response_model=ContributionRow,
    status_code=status.HTTP_201_CREATED,
)
async def add_contribution(
    debenture_id: Uuid, body: ContributionIn, user: AuthUser, db: Db
) -> ContributionRow:
    try:
        return await service.add_contribution(db, str(debenture_id), body)
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None
    except service.FutureContributionError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _FUTURE) from None


@router.patch("/{debenture_id}/contributions/{operation_id}", response_model=ContributionRow)
async def update_contribution(
    debenture_id: Uuid, operation_id: Uuid, body: ContributionPatch, user: AuthUser, db: Db
) -> ContributionRow:
    try:
        return await service.update_contribution(db, str(debenture_id), str(operation_id), body)
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None
    except service.ContributionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NO_CONTRIBUTION) from None
    except service.FutureContributionError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _FUTURE) from None


@router.delete(
    "/{debenture_id}/contributions/{operation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_contribution(
    debenture_id: Uuid, operation_id: Uuid, user: AuthUser, db: Db
) -> None:
    try:
        await service.delete_contribution(db, str(debenture_id), str(operation_id))
    except service.DebentureNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None
    except service.ContributionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NO_CONTRIBUTION) from None
    except service.LinkedContributionError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "integralizacao_ligada",
                "message": "Ligada a uma transação: recategorize a transação para tirá-la.",
            },
        ) from None
