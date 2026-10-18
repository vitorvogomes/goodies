"""Story 5.3 — fechar na base real: fev/2025 é bloqueado pelo saldo PF divergente (P8); mar/2025
fecha com "fechar mesmo assim" das pendências `confirma`, e o snapshot é igual ao resumo ao vivo
no instante do fechamento (golden). Story 5.5: a leitura do mês fechado vem do snapshot com os
mesmos números, a prévia de reabrir sai vazia e `refechar --completar` grava a versão 2 igual."""

from __future__ import annotations

import asyncio
from datetime import date

import asyncpg
import pytest

from engines.closing import service as closing
from engines.closing.checks import run_checks
from scripts.ops.ancorar_saldo import FILES_DIR, anchor
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

TERMS = (
    "receitas",
    "trabalho",
    "resgates",
    "devolucoes",
    "gastos",
    "investido",
    "resultado_mes",
    "saldo_contas",
    "valor_investido",
    "patrimonio",
    "aplicado",
    "resultado_investimentos",
    "taxa_poupanca",
    "rentabilidade",
    "rentabilidade_mes",
    "rentabilidade_mes_real",
    "caixa_corretora",
    "a_caminho",
)


async def test_fechamento_golden() -> None:
    import main  # noqa: F401

    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            # a base fixada é anterior à âncora da Story 3.12: grava os saldos informados
            await anchor(conn, sorted(FILES_DIR.rglob("*.ofx")), write=True)
            feb = await run_checks(conn, date(2025, 2, 1))
            assert any(c.code == "saldo_pf_divergente" and c.kind == "bloqueia" for c in feb)
            march = date(2025, 3, 1)
            checks = await run_checks(conn, march)
            assert not [c for c in checks if c.kind == "bloqueia"], checks
            confirm = [c.code for c in checks if c.kind == "confirma"]
            live = await closing.build_month_summary(conn, march, date(2025, 3, 31))
            out = await closing.close_month(conn, march, confirm)
            assert out.version == 1
            row = await conn.fetchrow(
                "SELECT * FROM month_summary_totals WHERE month = $1 AND version = 1", march
            )
            for term in TERMS:
                assert row[term] == getattr(live, term), term
            frozen = await closing.month_summary(conn, march)
            assert frozen.source == "snapshot"
            assert frozen.receitas_por_pagador == live.receitas_por_pagador
            assert frozen.gastos_por_categoria == live.gastos_por_categoria
            assert (await closing.reopen_preview(conn, march)).rows == []
            again = await closing.refechar(conn, march, mode="completar")
            assert again.version == 2
            for term in TERMS:
                assert getattr(await closing.month_summary(conn, march), term) == getattr(
                    frozen, term
                ), term
        finally:
            await conn.close()
    finally:
        await restore_dados()


async def test_ajuste_real() -> None:
    """Story 5.6 na base real: recategorizar uma despesa de mar/2025 já fechado deixa o mês em
    `ajuste`, o congelado não muda e o aviso diz a métrica que mudaria."""
    import main  # noqa: F401
    from engines.closing import alerts as closing_alerts
    from engines.common.alerts import AlertContext
    from engines.common.month_status import month_status
    from engines.ledger import service as ledger

    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            await anchor(conn, sorted(FILES_DIR.rglob("*.ofx")), write=True)
            march = date(2025, 3, 1)
            checks = await run_checks(conn, march)
            await closing.close_month(conn, march, [c.code for c in checks if c.kind == "confirma"])
            frozen = await closing.month_summary(conn, march)
            tx = await conn.fetchrow(
                "SELECT t.id, t.category_id FROM transactions t JOIN categories c "
                "ON c.id = t.category_id WHERE t.date >= '2025-03-01' AND t.date < '2025-04-01' "
                "AND c.role = 'consumo' ORDER BY t.amount LIMIT 1"
            )
            invest = await conn.fetchval(
                "SELECT id FROM categories WHERE role = 'investimento' ORDER BY key LIMIT 1"
            )
            await ledger.categorize(
                conn,
                [ledger.CategoryChange(str(tx["id"]), str(invest), "manual")],
                cause="inline_edit",
            )
            assert await month_status().status(conn, march) == "ajuste"
            after = await closing.month_summary(conn, march)
            assert (after.gastos, after.investido) == (frozen.gastos, frozen.investido)
            ctx = AlertContext(
                today=date(2026, 10, 18), periodo=march, months=month_status(), owner_id="x"
            )
            alert = next(
                a
                for a in await closing_alerts.adjustment_alerts(conn, ctx)
                if a.key == "ajuste:2025-03"
            )
            assert "Se reabrir, " in alert.message and alert.action.label == "Reabrir mês"
        finally:
            await conn.close()
    finally:
        await restore_dados()
