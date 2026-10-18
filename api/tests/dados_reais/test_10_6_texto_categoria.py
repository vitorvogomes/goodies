"""Story 10.6 — revisão 0045 (o texto de categoria da v1 sai) sobre a base real.

restaura → `alembic upgrade 0044` → mede → `alembic upgrade 0045` → mede. Invariantes: contagem e
total por mês × categoria iguais (transações e custos fixos), o texto que sai é o próprio nome da
subcategoria (nada se perde), todo padrão de `match_patterns` já é regra, e a poupança de cada mês
continua a do baseline fixado (ADR-016).
"""

from __future__ import annotations

import asyncio
import os
import subprocess

import asyncpg
import pytest

from scripts.ops.compare_categorias import LABEL_BY_ID, diff, snapshot
from tests.dados_reais.conftest import restore_dados
from workers.dbops import API_DIR, alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

FIXED_COSTS = (
    "SELECT (SELECT c.name FROM categories c WHERE c.id = f.category_id) AS label, count(*) AS n, "
    "sum(f.amount) AS s FROM fixed_costs f GROUP BY 1 ORDER BY 1"
)


async def _fixed_costs(conn: asyncpg.Connection) -> dict[str, tuple[int, str]]:
    return {r["label"]: (int(r["n"]), str(r["s"])) for r in await conn.fetch(FIXED_COSTS)}


def _downgrade(dsn: str, target: str) -> None:
    env = {**os.environ, "DATABASE_URL": dsn}
    subprocess.run(["alembic", "downgrade", target], cwd=API_DIR, env=env, check=True)


async def _savings(conn: asyncpg.Connection) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT to_char(month, 'YYYY-MM') AS m, savings_rate FROM monthly_summary ORDER BY 1"
    )
    return {r["m"]: str(r["savings_rate"]) for r in rows}


async def test_texto_de_categoria_sai_sem_mudar_mes_x_categoria() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0044_metric_events")
        conn = await asyncpg.connect(dsn)
        try:
            by_text = await snapshot(conn, "t.category")
            before = await snapshot(conn, LABEL_BY_ID)
            fixed_before = await _fixed_costs(conn)
            savings_before = await _savings(conn)
            orphan_patterns = await conn.fetchval(
                "SELECT count(*) FROM categories c, unnest(c.match_patterns) p WHERE NOT EXISTS "
                "(SELECT 1 FROM category_rules r WHERE lower(r.pattern) = lower(p))"
            )
            rules_before = await conn.fetchval("SELECT count(*) FROM category_rules")
        finally:
            await conn.close()
        assert diff(by_text, before) == {}, "o texto que sai difere da subcategoria"
        assert orphan_patterns == 0

        await asyncio.to_thread(alembic_upgrade, dsn, "0045_drop_category_text")
        conn = await asyncpg.connect(dsn)
        try:
            after = await snapshot(conn, LABEL_BY_ID)
            fixed_after = await _fixed_costs(conn)
            savings_after = await _savings(conn)
            rules_after = await conn.fetchval("SELECT count(*) FROM category_rules")
            gone = await conn.fetchval(
                "SELECT count(*) FROM information_schema.columns WHERE "
                "(table_name, column_name) IN (('transactions', 'category'), "
                "('fixed_costs', 'category'), ('categories', 'match_patterns'))"
            )
        finally:
            await conn.close()
        assert diff(before, after) == {}
        assert fixed_after == fixed_before
        assert savings_after == savings_before
        assert rules_after == rules_before
        assert gone == 0

        # ida e volta: o downgrade recria o texto a partir do category_id e a revisão roda de novo
        await asyncio.to_thread(_downgrade, dsn, "0044_metric_events")
        await asyncio.to_thread(alembic_upgrade, dsn, "0045_drop_category_text")
        conn = await asyncpg.connect(dsn)
        try:
            assert diff(after, await snapshot(conn, LABEL_BY_ID)) == {}
            assert await _fixed_costs(conn) == fixed_after
        finally:
            await conn.close()
    finally:
        await restore_dados()
