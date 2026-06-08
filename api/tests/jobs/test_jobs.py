"""E3 — endpoints /api/v1/jobs/status e /api/v1/jobs/refresh."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from workers.refresh import JobSpec


async def _clear(pool: Any) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM job_runs")


async def _seed(pool: Any, job: str, last_run: datetime) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ($1, $2, true) "
            "ON CONFLICT (job) DO UPDATE SET last_run = $2",
            job,
            last_run,
        )


class TestJobsStatus:
    @pytest.mark.asyncio
    async def test_reports_stale_fresh_and_never_run(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        await _seed(pool, "price_crypto", now - timedelta(hours=3))  # ttl 2h -> vencido
        await _seed(pool, "price_b3", now - timedelta(hours=1))  # ttl 26h -> fresco
        resp = await api.get("/api/v1/jobs/status", headers=auth_headers)
        assert resp.status_code == 200
        by = {j["job"]: j for j in resp.json()}
        assert by["price_crypto"]["stale"] is True
        assert by["price_b3"]["stale"] is False
        assert by["wallet_scan"]["stale"] is True  # nunca rodou
        assert by["wallet_scan"]["last_run"] is None

    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/jobs/status")
        assert resp.status_code in (401, 403)


class TestJobsRefresh:
    @pytest.mark.asyncio
    async def test_refresh_runs_jobs(
        self,
        api: AsyncClient,
        auth_headers: dict,
        pool: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        await _clear(pool)
        calls: list[str] = []

        async def fake_run(_pool: Any) -> dict[str, Any]:
            calls.append("x")
            return {"fetched": 2}

        monkeypatch.setattr(
            "workers.refresh.default_jobs",
            lambda: [JobSpec("price_b3", fake_run, 3600)],
        )
        resp = await api.post("/api/v1/jobs/refresh?force=true", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ran"
        assert body["jobs"] == {"price_b3": "ok"}
        assert calls == ["x"]
