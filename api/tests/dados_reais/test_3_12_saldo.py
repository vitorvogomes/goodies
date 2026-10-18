"""Story 3.12 — âncora e conferência encadeada da conta PF na base real: modo só-saldo (nenhuma
transação nova), âncora no fim de jul/2024, um intervalo por par de OFX mensais, idempotente."""

from __future__ import annotations

import asyncio
from datetime import date

import asyncpg
import pytest

from scripts.ops.ancorar_saldo import FILES_DIR, anchor
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_ancora_e_conferencia_encadeada() -> None:
    files = sorted(FILES_DIR.rglob("*.ofx"))
    if not files:
        require_or_skip("OFX do Nubank ausentes")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            before = await conn.fetchval("SELECT count(*) FROM transactions")
            report = await anchor(conn, files, write=True)
            assert await conn.fetchval("SELECT count(*) FROM transactions") == before
            assert report.anchor is not None and report.anchor[0] == date(2024, 7, 31)
            months = {d.replace(day=1) for d, _ in report.balances}
            assert date(2024, 6, 1) not in months  # jun/2024 fora: o fluxo começa em jul/2024
            assert len(report.intervals) == len(report.balances) - 1
            stored = await conn.fetchrow(
                "SELECT opening_balance, opening_balance_date FROM accounts WHERE holder = 'pf'"
            )
            assert stored["opening_balance_date"] == date(2024, 7, 31)
            assert stored["opening_balance"] == report.opening
            again = await anchor(conn, files, write=True)
            assert [(i.end, i.difference) for i in again.intervals] == [
                (i.end, i.difference) for i in report.intervals
            ]
            print(
                f"\nconferência PF: {len(report.intervals)} intervalos, "
                f"{len(report.divergent)} divergentes: "
                f"{[(i.start.isoformat(), i.end.isoformat()) for i in report.divergent]}"
            )
        finally:
            await conn.close()
    finally:
        await restore_dados()
