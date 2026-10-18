"""Story 10.5 — métricas de sucesso num comando: SM-2..SM-C2 lidas das tabelas de fato e dos
eventos (sem gravar nada); SM-5 só cause = import; SM-6/SM-C1 só cause ∈ {review, inline_edit};
a SM-1 grava o início e cada abertura da planilha e mostra os dias seguidos sem abrir."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from scripts.ops import metricas


async def _events(conn: Any) -> tuple[str, list[str]]:
    from engines.common.owner import get_owner_id

    owner = await get_owner_id(conn)
    account = await conn.fetchval("SELECT id FROM accounts ORDER BY created_at LIMIT 1")
    cats = [r["id"] for r in await conn.fetch("SELECT id FROM categories LIMIT 2")]
    txs: list[str] = []
    for i in range(4):
        txs.append(
            str(
                await conn.fetchval(
                    "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
                    "description) VALUES ($1, '2097-05-05', -10, $2, 'expense', $3) RETURNING "
                    "id",
                    account,
                    cats[0],
                    f"sm {i}",
                )
            )
        )
    at = datetime(2097, 5, 5, 12)
    rows = [
        (txs[0], "rule", "import", at),
        (txs[1], "rule", "import", at),
        (txs[2], "rule", "import", at),
        (txs[3], "suggestion", "import", at),
        (txs[0], "manual", "inline_edit", at + timedelta(days=2)),  # corrigida depois
        (txs[1], "manual", "migration", at + timedelta(days=2)),  # migração não conta
    ]
    for tx, source, cause, when in rows:
        await conn.execute(
            "INSERT INTO categorization_events (user_id, transaction_id, before_category_id, "
            "after_category_id, source, cause, created_at) "
            "VALUES ($1, $2::uuid, $3, $4, $5, $6, $7)",
            owner,
            tx,
            cats[0],
            cats[1] if cause != "import" else cats[0],
            source,
            cause,
            when,
        )
    await conn.execute(
        "INSERT INTO alert_dismissals (key, fingerprint, dismissed_at) VALUES "
        "('teste:sm', 'x', '2097-05-06')"
    )
    return owner, txs


@pytest.mark.asyncio
async def test_metrics_read_only(pool: Any) -> None:
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await _events(conn)
            before = await conn.fetchval("SELECT count(*) FROM categorization_events")
            report = await metricas.compute(conn, date(2097, 5, 1), date(2097, 5, 1))
            after = await conn.fetchval("SELECT count(*) FROM categorization_events")
        finally:
            await tx.rollback()
    assert before == after  # só lê
    assert report.sm5_rule_pct == pytest.approx(75.0)  # 3 de 4 por regra; só cause = import
    assert sum(report.sm6_corrections_by_week.values()) == 1  # a migração não conta
    assert report.sm_c1_pct == pytest.approx(25.0)  # 1 das 4 automáticas corrigida depois
    assert report.sm_c2_dismissed == 1


@pytest.mark.asyncio
async def test_sm1_start_and_openings(pool: Any) -> None:
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await metricas.record(conn, "sm1_inicio", date(2097, 1, 1), scope="caixa")
            await metricas.record(conn, "planilha_aberta", date(2097, 1, 20), note="conferir saldo")
            await metricas.record(conn, "sm1_inicio", date(2097, 1, 10), scope="v2")
            streaks = await metricas.sm1(conn, today=date(2097, 2, 25))
        finally:
            await tx.rollback()
    by = {s.scope: s for s in streaks}
    assert by["caixa"].days == 55 and by["caixa"].last_opening is None  # só o v2 abriu
    assert by["v2"].days == 36 and by["v2"].last_opening == date(2097, 1, 20)
    assert by["caixa"].met and by["v2"].met  # ≥ 30 dias
