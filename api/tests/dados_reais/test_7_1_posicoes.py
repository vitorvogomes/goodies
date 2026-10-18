"""Story 7.1 na base real: o preço do consolidado B3 fica com a data dele (revisão 0036 corrige o
que o import antigo datou de hoje) e as Posições do mês somam o valor investido do resumo."""

from __future__ import annotations

import asyncio
from datetime import date

import asyncpg
import pytest

from engines.closing import service as closing
from engines.ingest import service as ingest_service
from scripts.ops import close_retro
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_preco_do_consolidado_e_posicoes() -> None:
    import main  # noqa: F401

    files = sorted(close_retro.CONSOLIDADOS_DIR.rglob("*.xlsx"))
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0035_summary_budget")
        conn = await asyncpg.connect(dsn)
        try:
            preview = await ingest_service.preview(conn, [(p.name, p.read_bytes()) for p in files])
            await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            # o estado que o import antigo deixou: preço do consolidado datado de hoje
            await conn.execute("UPDATE asset_prices SET fetched_at = now() WHERE source = 'b3'")
            assert await conn.fetchval("SELECT count(*) FROM asset_prices WHERE source = 'b3'")
        finally:
            await conn.close()
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            days = {
                r["d"]
                for r in await conn.fetch(
                    "SELECT (fetched_at AT TIME ZONE 'America/Sao_Paulo')::date AS d "
                    "FROM asset_prices WHERE source = 'b3'"
                )
            }
            assert days == {date(2026, 9, 30)}
            wrong = await conn.fetchval(
                "SELECT count(*) FROM asset_price_history WHERE source = 'b3' "
                "AND ref_date > '2026-09-30'"
            )
            assert wrong == 0
            report = await closing.positions(conn, "2026-09", "mes")
            summary = await closing.build_month_summary(conn, date(2026, 9, 1))
            assert report.valor == summary.valor_investido - summary.caixa_corretora
        finally:
            await conn.close()
    finally:
        await restore_dados()
