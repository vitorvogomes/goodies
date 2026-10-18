"""Story 5.2 — resumo do mês na base real (com os consolidados da B3 importados pelo protocolo):
set/2026 valorado pelo consolidado de 30/09/2026, a taxa de poupança igual à lista v2 fixada, e o
mês corrente igual ao Painel."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import asyncpg
import pytest

from engines.closing import service as closing
from engines.common.dates import today_brt
from engines.ingest import service as ingest_service
from engines.overview import service as overview
from scripts.ops.baseline import pinned_savings_v2
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import API_DIR, alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_resumo_do_mes_na_base_real() -> None:
    import main  # noqa: F401

    pinned = pinned_savings_v2()
    files = sorted((API_DIR.parent / "files" / "b3" / "relatorio-consolidado").rglob("*.xlsx"))
    if pinned is None or not files:
        require_or_skip("lista v2 fixada ou consolidados ausentes")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            preview = await ingest_service.preview(conn, [(p.name, p.read_bytes()) for p in files])
            await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            sept = await closing.build_month_summary(conn, date(2026, 9, 1))
            assert sept.as_of == date(2026, 9, 30)
            assert sept.coverage["B3"] == "consolidado de 30/09/2026"
            assert sept.patrimonio > 0 and sept.valor_por_classe.get("acoes_br", 0) > 0
            # Pct sai com 2 casas (AD-4); a lista fixada guarda 6.
            assert sept.taxa_poupanca == Decimal(pinned["2026-09"] or "0").quantize(Decimal("0.01"))
            current = today_brt().replace(day=1)
            summary = await closing.build_month_summary(conn, current)
            painel = await overview.painel(conn, current)
            assert painel.patrimonio.value == summary.patrimonio
            assert painel.resultado_mes.value == summary.resultado_mes
        finally:
            await conn.close()
    finally:
        await restore_dados()
