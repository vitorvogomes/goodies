"""A caixinha de cada transação (conciliação de 18/10/2026, P21): as opções e a escolha. O OFX do
Nubank deixou de trazer o nome da caixinha em 19/06/2026."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from engines.common.deps import AuthUser, Db
from engines.common.models import Uuid

from . import caixinhas

router = APIRouter(prefix="/api/v1/portfolio/caixinhas", tags=["portfolio:caixinhas"])


class CaixinhaOptionOut(BaseModel):
    key: str
    label: str
    asset_id: str | None = None  # None = "Saldo separado" (caixa da conta)


class CaixinhaChoiceIn(BaseModel):
    caixinha: str  # `assets.key` da caixinha ou "separado"


@router.get("", response_model=list[CaixinhaOptionOut])
async def list_caixinhas(user: AuthUser, db: Db) -> list[CaixinhaOptionOut]:
    return [
        CaixinhaOptionOut(key=o.key, label=o.label) for o in await caixinhas.caixinha_options(db)
    ]


@router.put("/transactions/{transaction_id}", response_model=CaixinhaOptionOut)
async def choose_caixinha(
    transaction_id: Uuid, body: CaixinhaChoiceIn, user: AuthUser, db: Db
) -> CaixinhaOptionOut:
    options = {o.key: o for o in await caixinhas.caixinha_options(db)}
    if body.caixinha not in options:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "caixinha_inexistente", "message": "Caixinha não existe."},
        )
    try:
        await caixinhas.assign_caixinha(db, str(transaction_id), body.caixinha)
    except caixinhas.NotCaixinhaError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "nao_e_caixinha",
                "message": "A transação não é aplicação nem resgate de caixinha.",
            },
        ) from None
    except LookupError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "transacao_inexistente", "message": "Transação não existe."},
        ) from None
    option = options[body.caixinha]
    return CaixinhaOptionOut(key=option.key, label=option.label, asset_id=option.asset_id)
