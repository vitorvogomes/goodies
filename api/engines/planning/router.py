"""Rotas da engine planning (AD-15): o plano do mês. O orçamento é lido por `closing` (AD-8)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db

from . import distribution_service, goals, service, summary, targets
from .models import AporteIn, DividasIn, MonthPlanOut

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])


def _month(mes: str) -> date:
    try:
        return parse_periodo(mes)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None


def _closed(what: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {"error": "mes_fechado", "message": f"Mês fechado: reabra para mudar {what}."},
    )


@router.put("/months/{mes}/dividas", response_model=MonthPlanOut)
async def set_dividas(mes: str, body: DividasIn, user: AuthUser, db: Db) -> MonthPlanOut:
    try:
        return await service.set_dividas(db, _month(mes), body.valor)
    except service.MonthClosedError:
        raise _closed("as dívidas") from None


@router.put("/months/{mes}/aporte", response_model=MonthPlanOut)
async def set_aporte(mes: str, body: AporteIn, user: AuthUser, db: Db) -> MonthPlanOut:
    """Story 8.4: o aporte planejado do mês (None = não definido)."""
    try:
        return await service.set_aporte(db, _month(mes), body.valor)
    except service.MonthClosedError:
        raise _closed("o aporte planejado") from None


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


# ---- Metas de alocação (Story 8.2) ----


@router.get("/targets", response_model=targets.TargetsOut)
async def get_targets(user: AuthUser, db: Db) -> targets.TargetsOut:
    return await targets.get_targets(db)


@router.post("/targets/preview", response_model=targets.PreviewOut)
async def preview_targets(body: targets.TargetsIn, user: AuthUser) -> targets.PreviewOut:
    errors = targets.check_sums(body)
    return targets.PreviewOut(ok=not errors, errors=errors)


@router.put("/targets", response_model=targets.TargetsOut)
async def save_targets(body: targets.TargetsIn, user: AuthUser, db: Db) -> targets.TargetsOut:
    try:
        return await targets.save_targets(db, body)
    except targets.InvalidTargets as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "error": "metas_invalidas",
                "message": exc.errors[0].message
                if exc.errors
                else "Classe ou ativo inválido para as metas.",
                "errors": [e.model_dump(mode="json") for e in exc.errors],
            },
        ) from None


# ---- Travas da distribuição (Story 8.6) ----


async def _lock(db: Db, mes: str, key: str, value: Decimal | None) -> None:
    try:
        await service.set_lock(db, _month(mes), key, value)
    except service.InvalidLockKey:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "trava_invalida", "message": "Linha desconhecida da distribuição."},
        ) from None
    except service.MonthClosedError:
        raise _closed("a distribuição") from None


@router.put("/months/{mes}/travas/{key}")
async def set_lock(mes: str, key: str, body: AporteIn, user: AuthUser, db: Db) -> dict[str, str]:
    """Trava a linha no valor (o resto redistribui na prévia)."""
    if body.valor is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "valor_ausente", "message": "Informe o valor da linha."},
        )
    await _lock(db, mes, key, body.valor)
    return {"status": "travado"}


@router.delete("/months/{mes}/travas/{key}")
async def delete_lock(mes: str, key: str, user: AuthUser, db: Db) -> dict[str, str]:
    """Destrava: a linha volta a ser sugerida."""
    await _lock(db, mes, key, None)
    return {"status": "destravado"}


# ---- Distribuição do aporte (Story 8.5) ----


@router.post("/distribution/preview", response_model=distribution_service.DistributionOut)
async def distribution_preview(
    body: distribution_service.PreviewIn, user: AuthUser, db: Db
) -> distribution_service.DistributionOut:
    return await distribution_service.preview(db, _month(body.mes), body.planejado, body.travas)


# ---- Resumo do aporte no Painel (Story 8.8) ----


@router.get("/months/{mes}/aporte/resumo", response_model=summary.AporteSummary)
async def aporte_summary(mes: str, user: AuthUser, db: Db) -> summary.AporteSummary:
    return await summary.aporte_summary(db, _month(mes))
