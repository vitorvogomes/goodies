"""Rotas da engine planning (AD-15): o plano do mês. O orçamento é lido por `closing` (AD-8)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import goals, service
from .models import DividasIn, MonthPlanOut

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])


@router.put("/months/{mes}/dividas", response_model=MonthPlanOut)
async def set_dividas(mes: str, body: DividasIn, user: AuthUser, db: Db) -> MonthPlanOut:
    try:
        month = parse_periodo(mes)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None
    try:
        return await service.set_dividas(db, month, body.valor)
    except service.MonthClosedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "mes_fechado", "message": "Mês fechado: reabra para mudar as dívidas."},
        ) from None


# ---- Objetivos (Story 8.1) ----

_GOAL_NOT_FOUND = {"error": "objetivo_inexistente", "message": "Objetivo não encontrado."}


@router.get("/goals", response_model=goals.GoalsOut)
async def list_goals(user: AuthUser, db: Db) -> goals.GoalsOut:
    return await goals.list_goals(db)


@router.post("/goals", response_model=goals.Goal, status_code=status.HTTP_201_CREATED)
async def create_goal(body: goals.GoalIn, user: AuthUser, db: Db) -> goals.Goal:
    return await goals.create_goal(db, body)


@router.patch("/goals/{goal_id}", response_model=goals.Goal)
async def update_goal(goal_id: str, body: goals.GoalPatch, user: AuthUser, db: Db) -> goals.Goal:
    try:
        return await goals.update_goal(db, goal_id, body)
    except goals.GoalNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _GOAL_NOT_FOUND) from None


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: str, user: AuthUser, db: Db) -> None:
    try:
        await goals.delete_goal(db, goal_id)
    except goals.GoalNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _GOAL_NOT_FOUND) from None
    except goals.ReserveIsFixed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "reserva_fixa", "message": "A reserva de emergência não pode ser excluída."},
        ) from None


@router.post("/goals/{goal_id}/assets", response_model=goals.Goal)
async def link_asset(goal_id: str, body: goals.LinkIn, user: AuthUser, db: Db) -> goals.Goal:
    try:
        await goals.link(db, goal_id, body.asset_id)
        return await goals.get_goal(db, goal_id)
    except goals.GoalNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _GOAL_NOT_FOUND) from None


@router.post("/goal-suggestions/{asset_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggestion(asset_id: str, user: AuthUser, db: Db) -> None:
    await goals.dismiss(db, asset_id)
