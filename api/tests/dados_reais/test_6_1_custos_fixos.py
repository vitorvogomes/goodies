"""Story 6.1 na base real: a revisão 0033 dá vigência aos custos fixos atuais desde jul/2024 (o
`refechar` retroativo os enxerga), é idempotente e o casamento do mês roda sobre a base."""

from __future__ import annotations

import asyncio
import importlib
from datetime import date

import asyncpg
import pytest

from engines.ledger import service as ledger
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_vigencia_e_casamento_na_base_real() -> None:
    import main  # noqa: F401

    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch("SELECT valid_from, valid_to, is_active FROM fixed_costs")
            assert rows, "base sem custos fixos"
            assert all(r["valid_from"] == date(2024, 7, 1) for r in rows)
            assert all(r["valid_to"] is None for r in rows if r["is_active"])
            migration = importlib.import_module("db.migrations.versions.0033_fixed_cost_payments")
            for statement in migration._UPGRADE:  # idempotente: rodar de novo não muda nada
                await conn.execute(statement)
            assert await conn.fetchval("SELECT count(*) FROM fixed_costs") == len(rows)
            for month in (date(2024, 7, 1), date(2026, 9, 1)):
                matches = await ledger.fixed_cost_matches(conn, month)
                assert len(matches) == len([r for r in rows if r["is_active"]])
                assert {m.status for m in matches} <= {"pago", "pendente", "manual"}
            sept = await ledger.fixed_cost_matches(conn, date(2026, 9, 1))
            assert sum(1 for m in sept if m.status == "pago") >= 1
        finally:
            await conn.close()
    finally:
        await restore_dados()
