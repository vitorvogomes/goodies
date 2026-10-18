"""Endpoints de frescor / catch-up (Pilar 0). Casca acima das engines (AD-1): vive em `workers/`
desde a Story 4.3.

GET  /api/v1/jobs/status   -> idade + estado (fresco/vencido) por job, do heartbeat.
POST /api/v1/jobs/refresh  -> "Atualizar tudo": roda os jobs vencidos (ou todos, force).

Router próprio (não health.py) — payload mais rico que o contrato {componente: status}.
"""

import json
from datetime import UTC, datetime
from typing import Annotated, Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db, get_pool
from workers.refresh import default_jobs, oldest_wallet_scan, refresh_stale, stats_partial

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class JobStatus(BaseModel):
    job: str
    last_run: datetime | None
    ok: bool | None
    error: str | None
    stale: bool
    age_seconds: float | None
    data_age_seconds: float | None = None  # wallet_scan: idade do scanned_at real
    stats: dict[str, Any] | None = None
    status: str = "stale"  # fresh | stale | error | partial


def _derive_status(ok: bool | None, stale: bool, stats: Any) -> str:
    if ok is False:
        return "error"
    if stale:
        return "stale"
    if stats_partial(stats):
        return "partial"
    return "fresh"


@router.get("/status", response_model=list[JobStatus])
async def jobs_status(user: AuthUser, db: Db) -> list[JobStatus]:
    now = datetime.now(UTC)
    rows = {
        r["job"]: r for r in await db.fetch("SELECT job, last_run, ok, error, stats FROM job_runs")
    }
    # idade do DADO de carteira (não do heartbeat): um scan que rodou mas não trouxe
    # nada renova last_run sem renovar scanned_at — /refresh e /wallets divergiam
    oldest_scan = await oldest_wallet_scan(db)
    out: list[JobStatus] = []
    for spec in default_jobs():
        r = rows.get(spec.name)
        if r is None:  # nunca rodou -> vencido
            out.append(
                JobStatus(
                    job=spec.name,
                    last_run=None,
                    ok=None,
                    error=None,
                    stale=True,
                    age_seconds=None,
                    status="stale",
                )
            )
            continue
        age = (now - r["last_run"]).total_seconds()
        raw_stats = r["stats"]
        stats = json.loads(raw_stats) if isinstance(raw_stats, str) else raw_stats
        data_age: float | None = None
        stale = age >= spec.threshold_seconds
        if spec.name == "wallet_scan" and oldest_scan is not None:
            data_age = (now - oldest_scan).total_seconds()
            stale = data_age >= spec.threshold_seconds
        out.append(
            JobStatus(
                job=spec.name,
                last_run=r["last_run"],
                ok=r["ok"],
                error=r["error"],
                stale=stale,
                age_seconds=age,
                data_age_seconds=data_age,
                stats=stats if isinstance(stats, dict) else None,
                status=_derive_status(r["ok"], stale, stats),
            )
        )
    return out


class RefreshResult(BaseModel):
    status: str
    jobs: dict[str, str]


@router.post("/refresh", response_model=RefreshResult)
async def jobs_refresh(
    user: AuthUser,
    force: Annotated[bool, Query()] = False,
) -> RefreshResult:
    # usa o pool (refresh_stale adquire conexões próprias + os workers usam o pool)
    result = await refresh_stale(get_pool(), now=datetime.now(UTC), force=force)
    return RefreshResult(status=result["status"], jobs=result["jobs"])
