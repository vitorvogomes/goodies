"""Andamento do aporte do mês (Story 8.7 — FR-31, AR20): realizado total = o investimento do mês do
`ledger` (o mesmo número da Story 6.7, com o a caminho); realizado por linha = só o que virou ativo
(operações do mês de cada ativo; no bloco cripto, o que saiu para as carteiras); pendente =
planejado − realizado total. Cada mês começa do zero (o pendente não carrega)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.owner import get_owner_id
from engines.ledger import service as ledger_service
from engines.portfolio import positions as portfolio_positions

from . import calc, goals
from .service import month_plan

_CRYPTO_CLASS = "cripto"


@dataclass(frozen=True)
class MonthProgress:
    planned: Decimal | None  # None = não definido
    realizado: Decimal
    by_line: dict[str, Decimal]  # goal:<id> | class:<classe> | asset:<id> → realizado em ativo
    by_class: dict[str, Decimal]  # classe → realizado (sem os objetivos)
    by_asset: dict[str, Decimal]  # asset_id → realizado


async def month_progress(conn: asyncpg.Connection, month: date) -> MonthProgress:
    plan = await month_plan(conn, month)
    facts = await ledger_service.budget_facts(conn, month)
    owner = await get_owner_id(conn)
    by_asset, crypto = await portfolio_positions.month_contributions(conn, owner, month)
    linked = await goals.linked_assets(conn)
    classes = {
        r["id"]: r["class"]
        for r in await conn.fetch(
            "SELECT id::text AS id, class FROM assets WHERE id = ANY($1::uuid[])", list(by_asset)
        )
    }
    by_line: dict[str, Decimal] = {}
    by_class: dict[str, Decimal] = {}
    for asset, value in by_asset.items():
        by_line[f"asset:{asset}"] = value
        if asset in linked:
            key = f"goal:{linked[asset]}"
        else:
            cls = classes.get(asset, "")
            by_class[cls] = by_class.get(cls, Decimal(0)) + value
            key = f"class:{cls}"
        by_line[key] = by_line.get(key, Decimal(0)) + value
    if crypto:
        by_class[_CRYPTO_CLASS] = by_class.get(_CRYPTO_CLASS, Decimal(0)) + crypto
        key = f"class:{_CRYPTO_CLASS}"
        by_line[key] = by_line.get(key, Decimal(0)) + crypto
    return MonthProgress(
        planned=plan.aporte_planejado,
        realizado=facts.investido,
        by_line=by_line,
        by_class=by_class,
        by_asset=by_asset,
    )


def summary(p: MonthProgress, sugerido: dict[str, Decimal], planned: Decimal) -> calc.Progress:
    """O andamento sobre as linhas da distribuição (objetivos e classes), com o planejado dela (o
    do mês ou o da prévia)."""
    top = {k: v for k, v in p.by_line.items() if not k.startswith("asset:")}
    return calc.aporte_progress(planned, p.realizado, sugerido, top)
