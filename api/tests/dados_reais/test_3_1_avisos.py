"""Story 3.1 — Central de avisos na base real: com 3 meses em ajuste, `GET /api/v1/alerts` (10
leituras) fica com p95 abaixo de 500 ms; os providers do main rodam sem erro sobre o histórico."""

from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Any

import asyncpg
import pytest

from engines.alerts import service as alerts_service
from engines.common.month_status import (
    AllMonthsOpen,
    MonthState,
    month_status,
    register_month_status,
)
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

AJUSTE = {date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)}


class TresMesesEmAjuste(AllMonthsOpen):
    async def status(self, conn: Any, month: date) -> MonthState:
        return "ajuste" if month in AJUSTE else "aberto"


async def test_p95_da_central_com_meses_em_ajuste() -> None:
    import main  # noqa: F401 — registra os providers reais

    dsn = await restore_dados()
    original = month_status()
    register_month_status(TresMesesEmAjuste())
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            await alerts_service.active_alerts(conn)  # aquece
            took = []
            for _ in range(10):
                t0 = time.perf_counter()
                result = await alerts_service.active_alerts(conn)
                took.append(time.perf_counter() - t0)
        finally:
            await conn.close()
        p95 = sorted(took)[int(0.95 * len(took)) - 1]
        assert p95 < 0.5, f"p95 {p95:.3f}s"
        assert result.data_until is not None and result.data_until >= date(2026, 10, 1)
        assert all(a.severity in ("divergencia", "aviso") for a in result.items)
    finally:
        register_month_status(original)
        await restore_dados()
