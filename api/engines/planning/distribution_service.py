"""A Distribuição do aporte a partir da base (Story 8.5): o planejado e as travas do mês
(`month_plans`), os objetivos (`goals`), as metas do mês e as posições atuais sem os objetivos
(AD-11) → `distribution.distribute` (pura). Tudo calculado aqui; o front só mostra (AD-4)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel, Field

from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id
from engines.portfolio.positions import GOALS_BLOCK

from . import allocation, goals, targets
from .distribution import AssetState, ClassState, GoalNeed, distribute, months_until
from .service import month_plan


class PreviewIn(BaseModel):
    mes: str
    planejado: Money | None = Field(default=None, ge=0)  # None = o do mês
    travas: dict[str, Money] | None = None  # None = as gravadas no mês


class AssetOut(BaseModel):
    id: str
    label: str
    meta: Pct | None
    atual: Pct
    sugerido: Money | None
    locked: bool


class ClassOut(BaseModel):
    cls: str
    label: str
    meta: Pct
    atual: Pct
    desvio: Pct
    banda: Pct
    floor: Money
    sugerido: Money
    floor_only: bool
    out_of_band: bool
    locked: bool
    assets: list[AssetOut]


class GoalOut(BaseModel):
    id: str
    name: str
    kind: str
    target: Money
    current: Money
    progress: Pct
    deadline: date | None
    monthly: Money
    sugerido: Money
    locked: bool


class DistributionOut(BaseModel):
    month: date
    aporte_definido: bool
    planned: Money
    goals: list[GoalOut]
    classes: list[ClassOut]
    floors_reduced: bool
    locks_total: Money
    locks_over: bool  # "Travas somam R$ {x}, acima do planejado."
    has_targets: bool
    unassigned: Money


async def month_locks(conn: asyncpg.Connection, month: date) -> dict[str, Decimal]:
    raw = await conn.fetchval("SELECT travas FROM month_plans WHERE month = $1", month)
    return {k: Decimal(str(v)) for k, v in (json.loads(raw) if raw else {}).items()}


async def preview(
    conn: asyncpg.Connection,
    month: date,
    planned: Decimal | None = None,
    locks: dict[str, Decimal] | None = None,
) -> DistributionOut:
    plan = await month_plan(conn, month)
    defined = planned is not None or plan.aporte_planejado is not None
    amount = planned if planned is not None else (plan.aporte_planejado or Decimal(0))
    locks = locks if locks is not None else await month_locks(conn, month)

    goal_list = (await goals.list_goals(conn)).goals
    needs = [
        GoalNeed(
            id=g.id,
            name=g.name,
            kind=g.kind,
            target=g.target,
            current=g.valor,
            months=(g.horizon_months or 12)
            if g.kind == "reserva"
            else months_until(month, g.deadline or month),
            deadline=g.deadline,
        )
        for g in goal_list
    ]
    owner = await get_owner_id(conn)
    class_rows = await targets.class_targets(conn, month=month)
    asset_rows = await targets.asset_targets(conn, month=month)
    labels = dict(targets.CLASS_LABELS)
    states: list[ClassState] = []
    for c in await allocation.current_classes(conn, owner, month):
        if c.key == GOALS_BLOCK:
            continue
        row = class_rows.get(c.key)
        own = asset_rows.get(c.key, {})
        states.append(
            ClassState(
                cls=c.key,
                label=labels.get(c.key, c.label),
                value=c.valor,
                target_pct=Decimal(row["target_pct"]) if row else Decimal(0),
                band_pp=Decimal(row["band_pp"]) if row else Decimal(0),
                floor=Decimal(row["floor"]) if row else Decimal(0),
                assets=[
                    AssetState(
                        id=a.asset_id or a.symbol,
                        label=a.symbol,
                        value=a.valor.value or Decimal(0),
                        target_pct=own.get(a.asset_id or ""),
                    )
                    for a in c.assets
                ],
            )
        )
    d = distribute(amount, needs, states, locks)
    progress = {g.id: g.progress for g in goal_list}
    return DistributionOut(
        month=month,
        aporte_definido=defined,
        planned=amount,
        goals=[
            GoalOut(**{**vars(g), "progress": progress.get(g.id, Decimal(0))}) for g in d.goals
        ],
        classes=[
            ClassOut(
                **{k: v for k, v in vars(c).items() if k != "assets"},
                assets=[AssetOut(**vars(a)) for a in c.assets],
            )
            for c in d.classes
        ],
        floors_reduced=d.floors_reduced,
        locks_total=d.locks_total,
        locks_over=d.locks_total > amount,
        has_targets=d.has_targets,
        unassigned=d.unassigned,
    )
