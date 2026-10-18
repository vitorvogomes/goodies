"""Objetivos vinculados às caixinhas (Story 8.1 — FR-17, FR-35, AD-11): `goals` e `goal_assets` são
de `planning`. A reserva de emergência é fixa: alvo = multiplicador × custos fixos do mês, horizonte
editável. A caixinha sem decisão em `goal_assets` é sugerida; o vínculo só vale confirmado.
Progresso = valor atual dos ativos vinculados (o preço do CDI real), com o aportado líquido ao lado.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from engines.common.dates import today_brt
from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id
from engines.ledger import service as ledger_service
from engines.portfolio import calc as portfolio_calc
from engines.portfolio import service as portfolio_service

_CENT = Decimal("0.01")
_CAIXINHA = "caixinha:"
_NOT_A_GOAL = {"caixinha:encerradas"}  # o bucket das encerradas (Story 7.5) não é caixinha viva


class GoalNotFound(Exception):
    pass


class ReserveIsFixed(Exception):
    pass


class GoalIn(BaseModel):
    name: str = Field(min_length=1)
    target: Decimal = Field(gt=0)
    deadline: date
    asset_ids: list[str] = Field(default_factory=list)


class GoalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    target: Decimal | None = Field(default=None, gt=0)
    deadline: date | None = None
    asset_ids: list[str] | None = None
    multiplier: Decimal | None = Field(default=None, gt=0)  # só a reserva
    horizon_months: int | None = Field(default=None, gt=0)  # só a reserva


class LinkIn(BaseModel):
    asset_id: str


class GoalAsset(BaseModel):
    asset_id: str
    label: str
    valor: Money | None  # None = sem preço
    aportado: Money


class Goal(BaseModel):
    id: str
    kind: str  # reserva | objetivo
    name: str
    target: Money
    deadline: date | None
    multiplier: float | None
    horizon_months: int | None
    assets: list[GoalAsset]
    valor: Money
    aportado: Money
    progress: Pct  # valor ÷ alvo, em %


class Suggestion(BaseModel):
    asset_id: str
    label: str  # "Caixinha SnowTrip"
    goal_id: str | None  # o objetivo cujo nome casa com a caixinha (a reserva para a Reserva)
    goal_name: str | None


class GoalsOut(BaseModel):
    goals: list[Goal]
    suggestions: list[Suggestion]


def asset_label(key: str, name: str) -> str:
    if key.startswith(_CAIXINHA):
        return f"Caixinha {name.removeprefix('Nubank-')}"
    return name


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower() if ch.isalnum())


async def fixed_costs_total(conn: asyncpg.Connection, month: date) -> Decimal:
    """Custos fixos do mês pelo valor cadastrado (a base do alvo da reserva)."""
    return sum((r["amount"] for r in await ledger_service.fixed_costs_due(conn, month)), Decimal(0))


async def linked_assets(conn: asyncpg.Connection) -> dict[str, str]:
    """asset_id → goal_id dos vínculos confirmados (a base da alocação os exclui — Story 8.3)."""
    rows = await conn.fetch(
        "SELECT asset_id::text AS asset, goal_id::text AS goal FROM goal_assets "
        "WHERE status = 'confirmed'"
    )
    return {r["asset"]: r["goal"] for r in rows}


async def _asset_values(
    conn: asyncpg.Connection, assets: list[asyncpg.Record]
) -> dict[str, tuple[Decimal | None, Decimal]]:
    """asset_id → (valor atual, aportado líquido)."""
    if not assets:
        return {}
    owner = await get_owner_id(conn)
    positions = {
        p["asset_symbol"]: p["valor_atual"]
        for p in await portfolio_service.calculate_positions(conn, owner)
    }
    ops = await conn.fetch(
        "SELECT asset_id::text AS asset, tipo, quantidade, valor_unitario FROM asset_operations "
        "WHERE asset_id = ANY($1::uuid[])",
        [str(a["id"]) for a in assets],
    )
    by_asset: dict[str, list[Any]] = {}
    for op in ops:
        by_asset.setdefault(op["asset"], []).append(op)
    out: dict[str, tuple[Decimal | None, Decimal]] = {}
    for a in assets:
        value = positions.get(a["price_ref"])
        aportado = portfolio_calc.net_contributed(by_asset.get(str(a["id"]), []))
        out[str(a["id"])] = (
            Decimal(repr(value)).quantize(_CENT) if value is not None else None,
            aportado.quantize(_CENT),
        )
    return out


async def list_goals(conn: asyncpg.Connection) -> GoalsOut:
    month = today_brt().replace(day=1)
    costs = await fixed_costs_total(conn, month)
    goals = await conn.fetch(
        "SELECT * FROM goals ORDER BY kind = 'reserva' DESC, deadline NULLS LAST, name"
    )
    assets = await conn.fetch(
        "SELECT a.id, a.key, a.name, a.price_ref, ga.goal_id::text AS goal, ga.status "
        "FROM assets a LEFT JOIN goal_assets ga ON ga.asset_id = a.id "
        "WHERE ga.status = 'confirmed' OR (a.key LIKE 'caixinha:%' AND a.is_active "
        "AND ga.asset_id IS NULL AND a.key <> ALL($1::text[]))",
        list(_NOT_A_GOAL),
    )
    values = await _asset_values(conn, list(assets))
    out: list[Goal] = []
    for g in goals:
        gid = str(g["id"])
        reserve = g["kind"] == "reserva"
        target = (
            (Decimal(g["multiplier"]) * costs).quantize(_CENT) if reserve else Decimal(g["target"])
        )
        own = [a for a in assets if a["goal"] == gid and a["status"] == "confirmed"]
        items = [
            GoalAsset(
                asset_id=str(a["id"]),
                label=asset_label(a["key"], a["name"]),
                valor=values[str(a["id"])][0],
                aportado=values[str(a["id"])][1],
            )
            for a in own
        ]
        valor = sum((i.valor or Decimal(0) for i in items), Decimal(0))
        out.append(
            Goal(
                id=gid,
                kind=g["kind"],
                name=g["name"],
                target=target,
                deadline=g["deadline"],
                multiplier=float(g["multiplier"]) if g["multiplier"] is not None else None,
                horizon_months=g["horizon_months"],
                assets=items,
                valor=valor,
                aportado=sum((i.aportado for i in items), Decimal(0)),
                progress=(valor / target * 100).quantize(_CENT) if target > 0 else Decimal(0),
            )
        )
    reserve_goal = next((g for g in out if g.kind == "reserva"), None)

    def match(key: str, name: str) -> Goal | None:
        if key == "caixinha:reserva":
            return reserve_goal
        slug = _norm(name.removeprefix("Nubank-"))
        return next(
            (g for g in out if g.kind == "objetivo" and slug and slug in _norm(g.name)), None
        )

    suggestions = []
    for a in assets:
        if a["status"] is not None:
            continue
        goal = match(a["key"], a["name"])
        suggestions.append(
            Suggestion(
                asset_id=str(a["id"]),
                label=asset_label(a["key"], a["name"]),
                goal_id=goal.id if goal else None,
                goal_name=goal.name if goal else None,
            )
        )
    return GoalsOut(goals=out, suggestions=suggestions)


async def _goal(conn: asyncpg.Connection, goal_id: str) -> asyncpg.Record:
    row = await conn.fetchrow("SELECT * FROM goals WHERE id::text = $1", goal_id)
    if row is None:
        raise GoalNotFound(goal_id)
    return row


async def get_goal(conn: asyncpg.Connection, goal_id: str) -> Goal:
    await _goal(conn, goal_id)
    return next(g for g in (await list_goals(conn)).goals if g.id == goal_id)


async def _set_assets(conn: asyncpg.Connection, goal_id: str, asset_ids: list[str]) -> None:
    """Os ativos confirmados do objetivo passam a ser exatamente `asset_ids` (o que sai volta a ser
    sugerido)."""
    await conn.execute(
        "DELETE FROM goal_assets WHERE goal_id = $1::uuid AND asset_id <> ALL($2::uuid[])",
        goal_id,
        asset_ids,
    )
    for asset in asset_ids:
        await link(conn, goal_id, asset)


async def link(conn: asyncpg.Connection, goal_id: str, asset_id: str) -> None:
    await _goal(conn, goal_id)
    await conn.execute(
        "INSERT INTO goal_assets (asset_id, goal_id, status) VALUES ($1::uuid, $2::uuid, "
        "'confirmed') ON CONFLICT (asset_id) DO UPDATE SET goal_id = EXCLUDED.goal_id, "
        "status = 'confirmed', decided_at = now()",
        asset_id,
        goal_id,
    )


async def dismiss(conn: asyncpg.Connection, asset_id: str) -> None:
    """"Não é objetivo": a caixinha deixa de ser sugerida."""
    await conn.execute(
        "INSERT INTO goal_assets (asset_id, goal_id, status) VALUES ($1::uuid, NULL, 'dismissed') "
        "ON CONFLICT (asset_id) DO UPDATE SET goal_id = NULL, status = 'dismissed', "
        "decided_at = now()",
        asset_id,
    )


async def create_goal(conn: asyncpg.Connection, body: GoalIn) -> Goal:
    async with conn.transaction():
        goal_id = str(
            await conn.fetchval(
                "INSERT INTO goals (kind, name, target, deadline) VALUES ('objetivo', $1, $2, $3) "
                "RETURNING id",
                body.name.strip(),
                body.target,
                body.deadline,
            )
        )
        await _set_assets(conn, goal_id, body.asset_ids)
    return await get_goal(conn, goal_id)


async def update_goal(conn: asyncpg.Connection, goal_id: str, body: GoalPatch) -> Goal:
    current = await _goal(conn, goal_id)
    reserve = current["kind"] == "reserva"
    async with conn.transaction():
        await conn.execute(
            "UPDATE goals SET name = coalesce($2, name), target = CASE WHEN kind = 'reserva' "
            "THEN NULL ELSE coalesce($3, target) END, deadline = CASE WHEN kind = 'reserva' "
            "THEN NULL ELSE coalesce($4, deadline) END, multiplier = CASE WHEN kind = 'reserva' "
            "THEN coalesce($5, multiplier) END, horizon_months = CASE WHEN kind = 'reserva' "
            "THEN coalesce($6, horizon_months) END WHERE id = $1::uuid",
            goal_id,
            body.name.strip() if body.name and not reserve else None,
            body.target,
            body.deadline,
            body.multiplier,
            body.horizon_months,
        )
        if body.asset_ids is not None:
            await _set_assets(conn, goal_id, body.asset_ids)
    return await get_goal(conn, goal_id)


async def delete_goal(conn: asyncpg.Connection, goal_id: str) -> None:
    if (await _goal(conn, goal_id))["kind"] == "reserva":
        raise ReserveIsFixed(goal_id)
    await conn.execute("DELETE FROM goals WHERE id = $1::uuid", goal_id)
