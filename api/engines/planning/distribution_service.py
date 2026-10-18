"""A Distribuição do aporte a partir da base (Story 8.5): o planejado e as travas do mês
(`month_plans`), os objetivos (`goals`), as metas do mês e as posições atuais sem os objetivos
(AD-11) → `distribution.distribute` (pura). Tudo calculado aqui; o front só mostra (AD-4)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id
from engines.portfolio.positions import GOALS_BLOCK

from . import allocation, goals, targets
from . import progress as progress_service
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
    realizado: Money = Decimal(0)  # Story 8.7: só o que virou ativo no mês
    pendente: Money | None = None  # sugerido − realizado


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
    realizado: Money = Decimal(0)
    pendente: Money = Decimal(0)


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
    realizado: Money = Decimal(0)
    pendente: Money = Decimal(0)


class Andamento(BaseModel):
    """Story 8.7: realizado total (com o a caminho), em ativo, a caminho e pendente do mês."""

    planned: Money
    realizado: Money
    em_ativo: Money
    a_caminho: Money
    pendente: Money
    pct_realizado: Pct | None  # realizado ÷ planejado
    # rodapé de conciliação: objetivos + classes (Σ sugerido, Σ pendente das linhas)
    sugerido_linhas: Money
    pendente_linhas: Money
    confere: bool  # Σ pendente das linhas = pendente total + a caminho (realizado ≤ planejado)
    # Barra de progresso: trechos em % do planejado (em ativo sólido, a caminho hachurado)
    pct_em_ativo: Pct
    pct_a_caminho: Pct


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
    andamento: Andamento


def _share(part: Decimal, whole: Decimal) -> Decimal:
    """% de `part` em `whole`, entre 0 e 100 (a barra nunca passa do planejado)."""
    if whole <= 0:
        return Decimal(0)
    return min(Decimal(100), max(Decimal(0), part / whole * 100)).quantize(Decimal("0.01"))


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
    # a base é a posição antes do aporte do mês: o que entrou no mês sai dos valores, senão a
    # sugestão mudaria a cada aporte feito (e o plano pediria mais que o planejado)
    month_done = await progress_service.month_progress(conn, month)

    def before(value: Decimal, key: str) -> Decimal:
        return max(Decimal(0), value - month_done.by_line.get(key, Decimal(0)))

    needs = [
        GoalNeed(
            id=g.id,
            name=g.name,
            kind=g.kind,
            target=g.target,
            current=before(g.valor, f"goal:{g.id}"),
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
                value=before(c.valor, f"class:{c.key}"),
                target_pct=Decimal(row["target_pct"]) if row else Decimal(0),
                band_pp=Decimal(row["band_pp"]) if row else Decimal(0),
                floor=Decimal(row["floor"]) if row else Decimal(0),
                has_target=row is not None,
                assets=[
                    AssetState(
                        id=a.asset_id or a.symbol,
                        label=a.symbol,
                        value=before(a.valor.value or Decimal(0), f"asset:{a.asset_id}"),
                        target_pct=own.get(a.asset_id or ""),
                    )
                    for a in c.assets
                ],
            )
        )
    d = distribute(amount, needs, states, locks)
    progress = {g.id: g.progress for g in goal_list}
    sugerido = {f"goal:{g.id}": g.sugerido for g in d.goals}
    sugerido.update({f"class:{c.cls}": c.sugerido for c in d.classes})
    done = progress_service.summary(month_done, sugerido, amount)

    def line(key: str) -> tuple[Decimal, Decimal]:
        return done.lines.get(key, (Decimal(0), sugerido.get(key, Decimal(0))))

    def asset_line(a: Any) -> AssetOut:
        real = month_done.by_line.get(f"asset:{a.id}", Decimal(0))
        pend = a.sugerido - real if a.sugerido is not None else None
        return AssetOut(**vars(a), realizado=real, pendente=pend)

    return DistributionOut(
        month=month,
        aporte_definido=defined,
        planned=amount,
        goals=[
            GoalOut(
                **{**vars(g), "progress": progress.get(g.id, Decimal(0))},
                realizado=line(f"goal:{g.id}")[0],
                pendente=line(f"goal:{g.id}")[1],
            )
            for g in d.goals
        ],
        classes=[
            ClassOut(
                **{k: v for k, v in vars(c).items() if k != "assets"},
                assets=[asset_line(a) for a in c.assets],
                realizado=line(f"class:{c.cls}")[0],
                pendente=line(f"class:{c.cls}")[1],
            )
            for c in d.classes
        ],
        floors_reduced=d.floors_reduced,
        locks_total=d.locks_total,
        locks_over=d.locks_total > amount,
        has_targets=d.has_targets,
        unassigned=d.unassigned,
        andamento=Andamento(
            planned=amount,
            realizado=done.realizado,
            em_ativo=done.em_ativo,
            a_caminho=done.a_caminho,
            pendente=done.pendente,
            pct_realizado=(done.realizado / amount * 100).quantize(Decimal("0.01"))
            if amount > 0
            else None,
            sugerido_linhas=sum(sugerido.values(), Decimal(0)),
            pendente_linhas=sum((p for _, p in done.lines.values()), Decimal(0)),
            confere=sum((p for _, p in done.lines.values()), Decimal(0))
            == done.pendente + done.a_caminho,
            pct_em_ativo=_share(done.em_ativo, amount),
            pct_a_caminho=min(
                Decimal(100) - _share(done.em_ativo, amount), _share(done.a_caminho, amount)
            ),
        ),
    )
