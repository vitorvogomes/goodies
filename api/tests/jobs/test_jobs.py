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
        # Story 10.3: nome na tela, último sucesso e próxima execução (pelo cron registrado)
        assert by["price_b3"]["label"] == "Preços B3 e Tesouro"
        assert "last_success_at" in by["price_b3"]
        assert by["wallet_scan"]["note"] and "Binance" in by["wallet_scan"]["note"]
        assert all(j["next_run"] is not None for j in by.values())
        assert datetime.fromisoformat(by["db_backup"]["next_run"]) > now

    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.get("/api/v1/jobs/status")
        assert resp.status_code in (401, 403)


async def _seed_with_stats(
    pool: Any, job: str, last_run: datetime, stats: dict[str, Any], *, ok: bool = True
) -> None:
    import json

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok, stats) "
            "VALUES ($1, $2, $3, $4::jsonb) "
            "ON CONFLICT (job) DO UPDATE SET last_run = $2, ok = $3, stats = $4::jsonb",
            job,
            last_run,
            ok,
            json.dumps(stats),
        )


class TestJobsStatusHonesty:
    """Frescor honesto: stats com falha viram `partial`; wallet_scan envelhece pelo
    `scanned_at` real das posições (não pelo heartbeat) — /refresh e /wallets coerentes."""

    @pytest.mark.asyncio
    async def test_wallet_scan_stale_by_scanned_at_even_if_just_ran(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        # heartbeat diz "rodou agora", mas o run não trouxe nada (fetched=0 em tudo)
        await _seed_with_stats(
            pool,
            "wallet_scan",
            now,
            {"EtherscanFetcher": {"fetched": 0, "failed": 0, "swept": 0}},
        )
        async with pool.acquire() as conn:
            uid = await conn.fetchval("SELECT id FROM users ORDER BY created_at LIMIT 1")
            await conn.execute(
                "INSERT INTO wallet_positions (user_id, chain, wallet_address, "
                "asset_symbol, quantity, source, scanned_at, is_manual) "
                "VALUES ($1, 'ethereum', '0xtest', 'ETH', 1, 'etherscan', $2, false)",
                uid,
                now - timedelta(hours=20),  # dado real tem 20h (> ttl 14h)
            )
        try:
            resp = await api.get("/api/v1/jobs/status", headers=auth_headers)
            assert resp.status_code == 200
            ws = {j["job"]: j for j in resp.json()}["wallet_scan"]
            assert ws["stale"] is True  # pela idade do DADO, não do heartbeat
            assert ws["status"] == "stale"
            assert ws["data_age_seconds"] is not None
            assert ws["data_age_seconds"] >= 19 * 3600
        finally:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM wallet_positions WHERE wallet_address = '0xtest'")

    @pytest.mark.asyncio
    async def test_wallet_scan_partial_when_nothing_fetched(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        await _seed_with_stats(
            pool,
            "wallet_scan",
            now,
            {
                "EtherscanFetcher": {"fetched": 0, "failed": 0, "swept": 0},
                "BinanceFetcher": {"fetched": 0, "failed": 0, "swept": 0},
            },
        )
        resp = await api.get("/api/v1/jobs/status", headers=auth_headers)
        ws = {j["job"]: j for j in resp.json()}["wallet_scan"]
        # sem wallet_positions não-manuais: não há idade de dado, mas o scan
        # que voltou de mãos vazias não pode aparecer como "fresh"
        assert ws["status"] == "partial"
        assert ws["stats"] is not None

    @pytest.mark.asyncio
    async def test_price_b3_partial_when_source_failed(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        await _seed_with_stats(
            pool,
            "price_b3",
            now,
            {
                "b3": {"symbols": 17, "fetched": 1, "updated": 1, "skipped": 0, "failed": 16},
                "tesouro": {"symbols": 7, "fetched": 7, "updated": 7, "skipped": 0, "failed": 0},
            },
        )
        resp = await api.get("/api/v1/jobs/status", headers=auth_headers)
        b3 = {j["job"]: j for j in resp.json()}["price_b3"]
        assert b3["status"] == "partial"
        assert b3["stale"] is False

    @pytest.mark.asyncio
    async def test_fresh_when_stats_clean_and_error_when_ok_false(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        await _seed_with_stats(
            pool,
            "price_b3",
            now,
            {
                "b3": {"symbols": 16, "fetched": 16, "updated": 16, "skipped": 0, "failed": 0},
                "tesouro": {"symbols": 0, "fetched": 0, "updated": 0, "skipped": 0, "failed": 0},
            },
        )
        await _seed_with_stats(pool, "price_crypto", now, {}, ok=False)
        by = {
            j["job"]: j for j in (await api.get("/api/v1/jobs/status", headers=auth_headers)).json()
        }
        assert by["price_b3"]["status"] == "fresh"  # tesouro symbols=0 não é falha
        assert by["price_crypto"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_crypto_partial_when_total_outage(
        self, api: AsyncClient, auth_headers: dict, pool: Any
    ) -> None:
        await _clear(pool)
        now = datetime.now(UTC)
        # CoinGecko 100% fora: símbolos pedidos, zero cotações (achado C8)
        await _seed_with_stats(
            pool,
            "price_crypto",
            now,
            {"symbols": 9, "fetched": 0, "updated": 0, "skipped": 0, "failed": 9},
        )
        resp = await api.get("/api/v1/jobs/status", headers=auth_headers)
        pc = {j["job"]: j for j in resp.json()}["price_crypto"]
        assert pc["status"] == "partial"


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
