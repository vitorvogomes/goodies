"""Story 5.5 — mês fechado lê o snapshot (nunca recalculado), reabrir mostra congelado × recalculado
só nas métricas de fluxo que mudam, fechar de novo cria a versão seguinte (as antigas ficam) e
`refechar --completar` copia o congelado e preenche só o que estava nulo/fora_do_resumo."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import service as closing

URL = "/api/v1/closing/months"
MONTH = date(2025, 6, 1)


@pytest.fixture
async def clean(pool: Any, account: str):
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM month_closes WHERE month = $1", MONTH)


async def _close(pool: Any) -> int:
    async with pool.acquire() as conn:
        checks = await closing.run_checks(conn, MONTH)
        if [c for c in checks if c.kind == "bloqueia"]:
            pytest.skip("mês de teste bloqueado no goodies_test")
        out = await closing.close_month(conn, MONTH, [c.code for c in checks])
    return out.version


@pytest.mark.asyncio
async def test_snapshot_reopen_and_versions(api, auth_headers, account, pool, clean) -> None:
    import main  # noqa: F401

    assert await _close(pool) == 1
    async with pool.acquire() as conn:
        frozen = await closing.month_summary(conn, MONTH)
        assert frozen.source == "snapshot"
        cat = await conn.fetchval(
            "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
        )
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
            "description, review_status, category_source) VALUES ($1::uuid, '2025-06-15', "
            "-123.45, $2, 'expense', $3, 'confirmed', 'manual')",
            account,
            cat,
            f"ajuste {uuid.uuid4().hex[:6]}",
        )
        still = await closing.month_summary(conn, MONTH)
    assert still.gastos == frozen.gastos  # nunca recalculado

    pv = (await api.get(f"{URL}/2025-06/reopen/preview", headers=auth_headers)).json()
    metrics = {r["metric"]: r for r in pv["rows"]}
    assert "gastos" in metrics and "receitas" not in metrics
    assert Decimal(str(metrics["gastos"]["live"])) - Decimal(
        str(metrics["gastos"]["frozen"])
    ) == Decimal("123.45")

    r = await api.post(f"{URL}/2025-06/reopen", headers=auth_headers)
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        assert (await closing.month_summary(conn, MONTH)).source == "live"
    assert await _close(pool) == 2
    async with pool.acquire() as conn:
        versions = await conn.fetchval("SELECT count(*) FROM month_closes WHERE month = $1", MONTH)
        latest = await closing.month_summary(conn, MONTH)
    assert versions == 2 and latest.gastos == frozen.gastos + Decimal("123.45")


@pytest.mark.asyncio
async def test_refechar_completar_fills_only_missing(pool, account, clean) -> None:
    import main  # noqa: F401

    await _close(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE month_summary_totals SET patrimonio = NULL, receitas = 999, "
            'unavailable = unavailable || \'{"patrimonio": "fora_do_resumo"}\'::jsonb '
            "WHERE month = $1",
            MONTH,
        )
        out = await closing.refechar(conn, MONTH, mode="completar")
        row = await conn.fetchrow(
            "SELECT * FROM month_summary_totals WHERE month = $1 AND version = $2",
            MONTH,
            out.version,
        )
        origin = await conn.fetchval(
            "SELECT origin FROM month_closes WHERE month = $1 AND version = $2", MONTH, out.version
        )
    assert out.version == 2
    assert row["receitas"] == Decimal("999.00")  # congelado copiado
    assert row["patrimonio"] is not None  # o que faltava, preenchido
    assert "patrimonio" not in json.loads(row["unavailable"])
    assert origin == "live"


def test_parse_months() -> None:
    from scripts.ops.refechar import parse_months

    assert parse_months("2025-11..2026-02") == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]
    assert parse_months("2026-06") == [date(2026, 6, 1)]
    with pytest.raises(ValueError):
        parse_months("2026-06..2026-01")


@pytest.mark.asyncio
async def test_refechar_script_recalcular_asks(pool, clean) -> None:
    import main  # noqa: F401
    from scripts.ops.refechar import run

    await _close(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE month_summary_totals SET gastos = gastos + 1 WHERE month = $1", MONTH
        )
        said: list[str] = []
        kept = await run(
            conn, [MONTH], mode="recalcular", confirm=lambda _: False, echo=said.append
        )
        assert kept == [] and any("Gastos" in s for s in said)
        done = await run(conn, [MONTH, date(2025, 7, 1)], mode="recalcular", echo=said.append)
        status = await conn.fetch(
            "SELECT version, status FROM month_closes WHERE month = $1 ORDER BY version", MONTH
        )
    assert done == [(MONTH, 2)]
    assert [(r["version"], r["status"]) for r in status] == [(1, "reopened"), (2, "closed")]
