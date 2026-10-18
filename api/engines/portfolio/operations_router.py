"""Operações dos ativos (Story 10.6 — o substituto da tela v1 /portfolio/history): a lista com os
filtros (ativo por trecho, tipo, período), com o total de cada operação calculado aqui (AD-4: o
front não multiplica dinheiro). Migra a leitura do legado `/api/v1/asset-operations`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from engines.common.deps import AuthUser, Db
from engines.common.money import Money
from engines.common.owner import get_owner_id

from . import operations

router = APIRouter(prefix="/api/v1/portfolio/operations", tags=["portfolio:operations"])

_CENT = Decimal("0.01")


class OperationRow(BaseModel):
    id: str
    data_operacao: date
    asset_symbol: str
    asset_category: str
    tipo: str
    quantidade: Decimal
    valor_unitario: Money
    total: Money  # quantidade × valor unitário


@router.get("", response_model=list[OperationRow])
async def list_operations(
    user: AuthUser,
    db: Db,
    asset_symbol: str | None = None,
    tipo: str | None = None,
    data_from: date | None = None,
    data_to: date | None = None,
) -> list[OperationRow]:
    rows = await operations.list_operations(
        db,
        user_id=await get_owner_id(db),
        asset_symbol=asset_symbol,
        tipo=tipo,
        data_from=data_from,
        data_to=data_to,
    )
    out: list[OperationRow] = []
    for r in rows:
        qty, unit = Decimal(str(r["quantidade"])), Decimal(str(r["valor_unitario"]))
        out.append(
            OperationRow(
                id=str(r["id"]),
                data_operacao=r["data_operacao"],
                asset_symbol=r["asset_symbol"],
                asset_category=r["asset_category"],
                tipo=r["tipo"],
                quantidade=qty,
                valor_unitario=unit,
                total=(qty * unit).quantize(_CENT),
            )
        )
    return out
