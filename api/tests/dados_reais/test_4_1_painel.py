"""Story 4.1 — Painel na base real, a frio (Redis vazio; nenhuma API externa é chamada na
leitura): 10 cargas com p95 abaixo de 3 s, e os KPIs do mês atual com valor e data."""

from __future__ import annotations

import asyncio
import time

import asyncpg
import pytest

from engines.common.dates import today_brt
from engines.overview import service as overview
from scripts.ops.baseline import frozen_prices
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_p95_do_painel_a_frio() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            month = today_brt().replace(day=1)
            took = []
            with frozen_prices():  # cache nulo: toda carga recalcula (XIRR inclusive)
                for _ in range(10):
                    t0 = time.perf_counter()
                    painel = await overview.painel(conn, month)
                    took.append(time.perf_counter() - t0)
        finally:
            await conn.close()
        p95 = sorted(took)[int(0.95 * len(took)) - 1]
        assert p95 < 3.0, f"p95 {p95:.2f}s"
        for kpi in (
            painel.patrimonio,
            painel.resultado_investimentos,
            painel.rentabilidade_nominal,
        ):
            assert kpi.value is not None and kpi.as_of is not None
        assert painel.resultado_mes.value is not None
        print(f"\npainel a frio: p95 {p95:.2f}s")
    finally:
        await restore_dados()
