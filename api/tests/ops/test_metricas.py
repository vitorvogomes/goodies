"""Story 10.5 — métricas de sucesso num comando: SM-2..SM-C2 lidas das tabelas de fato e dos
eventos (sem gravar nada); SM-5 só cause = import; SM-6/SM-C1 só cause ∈ {review, inline_edit};
a SM-1 grava o início e cada abertura da planilha e mostra os dias seguidos sem abrir."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from scripts.ops import metricas

BRT = ZoneInfo("America/Sao_Paulo")


async def _events(conn: Any) -> tuple[str, list[str]]:
    from engines.common.owner import get_owner_id

    owner = await get_owner_id(conn)
    account = await conn.fetchval("SELECT id FROM accounts ORDER BY created_at LIMIT 1")
    cats = [r["id"] for r in await conn.fetch("SELECT id FROM categories LIMIT 2")]
    at = datetime(2097, 5, 5, 12, tzinfo=BRT)
    batch = await conn.fetchval(
        "INSERT INTO import_batches (status, applied_at) VALUES ('applied', now()) RETURNING id"
    )
    txs: list[str] = []
    # 5 transações novas do import: 3 por regra, 1 por sugestão, 1 sem nada ("a classificar")
    for i in range(5):
        txs.append(
            str(
                await conn.fetchval(
                    "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
                    "description, source, batch_id, created_at) VALUES ($1, '2097-05-05', -10, $2, "
                    "'expense', $3, 'nubank_ofx', $4, $5) RETURNING id",
                    account,
                    cats[0],
                    f"sm {i}",
                    batch,
                    at,
                )
            )
        )
    legacy = await conn.fetchval(
        "INSERT INTO import_batches (status) VALUES ('legacy') RETURNING id"
    )
    await conn.execute(  # lote legado (a base anterior ao Hub): não é transação nova
        "INSERT INTO transactions (account_id, date, amount, category_id, kind, description, "
        "source, batch_id, created_at) VALUES ($1, '2097-05-05', -10, $2, 'expense', 'velha', "
        "'nubank_ofx', $3, $4)",
        account,
        cats[0],
        legacy,
        at,
    )
    later = at + timedelta(days=2)
    rows = [
        (txs[0], "rule", "import", at, cats[0]),
        (txs[1], "rule", "import", at, cats[0]),
        (txs[2], "rule", "import", at, cats[0]),
        (txs[3], "suggestion", "import", at, cats[0]),
        # tx0: confirmada na revisão sem mudar (não é correção) e corrigida depois → SM-C1
        (txs[0], "rule", "review", later, cats[0]),
        (txs[0], "manual", "inline_edit", later + timedelta(days=1), cats[1]),
        # tx2: trocada NA revisão (a revisão funcionando): correção da SM-6, não da SM-C1
        (txs[2], "manual", "review", later, cats[1]),
        (txs[1], "manual", "migration", later, cats[1]),  # migração não conta
    ]
    for tx, source, cause, when, after in rows:
        await conn.execute(
            "INSERT INTO categorization_events (user_id, transaction_id, before_category_id, "
            "after_category_id, source, cause, created_at) "
            "VALUES ($1, $2::uuid, $3, $4, $5, $6, $7)",
            owner,
            tx,
            cats[0],
            after,
            source,
            cause,
            when,
        )
    await conn.execute(
        "INSERT INTO alert_dismissals (key, fingerprint, dismissed_at) VALUES "
        "('teste:sm', 'x', '2097-05-06'), "
        # 31/05 23:30 em Brasília = 01/06 02:30 UTC: ainda é maio
        "('teste:fim', 'y', '2097-05-31 23:30-03')"
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
            june = await metricas.compute(conn, date(2097, 6, 1), date(2097, 6, 1))
            after = await conn.fetchval("SELECT count(*) FROM categorization_events")
        finally:
            await tx.rollback()
    assert before == after  # só lê
    # 3 por regra das 5 novas: a sem categoria entra no denominador
    assert report.sm5_rule_pct == pytest.approx(60.0)
    # correções: a troca na revisão e a correção depois; confirmar sem mudar e migração não
    assert sum(report.sm6_corrections_by_week.values()) == 2
    assert report.sm_c1_pct == pytest.approx(25.0)  # 1 das 4 automáticas corrigida depois
    assert report.sm_c2_dismissed == 2  # o de 31/05 23:30 (Brasília) é de maio
    assert june.sm_c2_dismissed == 0
    assert report.sm3_wallets_total >= report.sm3_wallets_ok


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
