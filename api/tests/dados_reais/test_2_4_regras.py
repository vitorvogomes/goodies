"""Story 2.4 — revisão 0019 (regras, origem da categoria, eventos) sobre a base real.

restaura → `upgrade 0018` → mede → `upgrade 0019` → mede. Totais mês x categoria e contagem
idênticos; toda transação com origem e estado de revisão; histórico `confirmed`, importado sem
revisão (ADR-016) `pending`; padrões de aplicação e resgate viram duas regras com direção.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from scripts.ops.compare_categorias import LABEL_BY_ID, diff, snapshot
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

CUTOFF = "'2026-10-18 06:07:00+00'"


async def test_regras_e_origem() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0018_category_groups")
        conn = await asyncpg.connect(dsn)
        try:
            before = await snapshot(conn, LABEL_BY_ID)
        finally:
            await conn.close()

        await asyncio.to_thread(alembic_upgrade, dsn, "0019_category_rules")

        conn = await asyncpg.connect(dsn)
        try:
            assert diff(before, await snapshot(conn, LABEL_BY_ID)) == {}
            missing = await conn.fetchval(
                "SELECT count(*) FROM transactions "
                "WHERE category_source IS NULL OR review_status IS NULL"
            )
            assert missing == 0
            states = dict(
                await conn.fetch(
                    f"SELECT created_at >= {CUTOFF} AS novo, "
                    "bool_and(review_status = CASE WHEN created_at >= "
                    f"{CUTOFF} THEN 'pending' ELSE 'confirmed' END) "
                    "FROM transactions GROUP BY 1"
                )
            )
            assert all(states.values())
            # histórico: só rule ou manual; regra aplicada aponta para a categoria da transação
            hist_sources = {
                r[0]
                for r in await conn.fetch(
                    f"SELECT DISTINCT category_source FROM transactions WHERE created_at < {CUTOFF}"
                )
            }
            assert hist_sources <= {"rule", "manual"}
            wrong_rule = await conn.fetchval(
                "SELECT count(*) FROM transactions t JOIN category_rules r "
                "ON r.id = t.category_rule_id WHERE r.category_id <> t.category_id"
            )
            assert wrong_rule == 0
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM transactions WHERE category_source = 'rule' "
                    "AND category_rule_id IS NULL"
                )
                == 0
            )
            # aplicação e resgate: duas regras por padrão (saída → investimento, entrada → resgate)
            for pattern in ("caixinha", "rdb", "dinheiro guardado"):
                pairs = {
                    (r["direction"], r["key"])
                    for r in await conn.fetch(
                        "SELECT r.direction, c.key FROM category_rules r "
                        "JOIN categories c ON c.id = r.category_id WHERE r.pattern = $1",
                        pattern,
                    )
                }
                assert pairs == {
                    ("saida", "invest:caixinha_rdb"),
                    ("entrada", "resgate:caixinha_rdb"),
                }, pattern
            # transferência interna não vira regra; legado Flash/Betuel aponta para Recorrente
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM category_rules r "
                    "JOIN categories c ON c.id = r.category_id "
                    "WHERE c.key = 'transfer:interna' OR c.key LIKE 'legado:%'"
                )
                == 0
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM category_rules r "
                    "JOIN categories c ON c.id = r.category_id "
                    "WHERE c.key = 'trabalho:recorrente'"
                )
                >= 1
            )
            assert await conn.fetchval("SELECT count(*) FROM categorization_events") == 0
            stats = dict(
                await conn.fetch("SELECT category_source, count(*) FROM transactions GROUP BY 1")
            )
            print("origem:", stats)
        finally:
            await conn.close()
    finally:
        await restore_dados()
