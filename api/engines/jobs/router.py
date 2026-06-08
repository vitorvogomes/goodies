"""Endpoints de frescor / catch-up (Pilar 0).

GET  /api/v1/jobs/status   -> idade + estado (fresco/vencido) por job, do heartbeat.
POST /api/v1/jobs/refresh  -> "Atualizar tudo": roda os jobs vencidos (ou todos, force).

Router próprio (não health.py) — payload mais rico que o contrato {componente: status}.
"""

from datetime import UTC, datetime
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth.dependencies import get_current_user
from db.connection import get_db, get_pool
from workers.refresh import default_jobs, refresh_stale

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


@router.get("/status", response_model=list[JobStatus])
async def jobs_status(user: AuthUser, db: Db) -> list[JobStatus]:
    now = datetime.now(UTC)
    rows = {
        r["job"]: r
        for r in await db.fetch("SELECT job, last_run, ok, error FROM job_runs")
    }
    out: list[JobStatus] = []
    for spec in default_jobs():
        r = rows.get(spec.name)
        if r is None:  # nunca rodou -> vencido
            out.append(
                JobStatus(
                    job=spec.name, last_run=None, ok=None, error=None,
                    stale=True, age_seconds=None,
                )
            )
            continue
        age = (now - r["last_run"]).total_seconds()
        out.append(
            JobStatus(
                job=spec.name, last_run=r["last_run"], ok=r["ok"], error=r["error"],
                stale=age >= spec.threshold_seconds, age_seconds=age,
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
