"""Rotas de caixa em corretora (Story 7.7 — AD-15): os Cartões de corretora da Conciliação e o
"Saldo que vejo na corretora"."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from engines.common.dates import today_brt
from engines.common.deps import AuthUser, Db
from engines.common.money import Money
from engines.common.owner import get_owner_id

from . import brokers as service

router = APIRouter(prefix="/api/v1/portfolio/brokers", tags=["portfolio:brokers"])


class BrokerCard(BaseModel):
    rail: str
    name: str
    saiu: Money
    proventos: Money
    aplicado: Money
    caixa: Money
    a_caminho: Money
    covered_until: date | None  # o relatório da corretora cobre até (Carimbo de data)
    import_from: date | None  # importar o relatório B3 a partir de
    informed: Money | None
    informed_at: date | None
    divergent: bool


class BrokerCheckIn(BaseModel):
    rail: str
    as_of: date
    balance: Money


def _card(b: service.BrokerCash) -> BrokerCard:
    return BrokerCard(
        rail=b.rail,
        name=b.name,
        saiu=b.saiu,
        proventos=b.proventos,
        aplicado=b.aplicado,
        caixa=b.caixa,
        a_caminho=b.a_caminho,
        covered_until=b.covered_until,
        import_from=b.import_from,
        informed=b.informed,
        informed_at=b.informed_at,
        divergent=b.divergent,
    )


@router.get("", response_model=list[BrokerCard])
async def brokers(user: AuthUser, db: Db) -> list[BrokerCard]:
    owner = await get_owner_id(db)
    return [_card(b) for b in await service.broker_cash_as_of(db, owner, today_brt())]


@router.post("/checks", response_model=list[BrokerCard])
async def save_check(body: BrokerCheckIn, user: AuthUser, db: Db) -> list[BrokerCard]:
    try:
        await service.save_check(db, body.rail, body.as_of, body.balance)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "corretora_invalida", "message": "Corretora desconhecida."},
        ) from None
    return await brokers(user, db)
