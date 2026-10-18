"""Story 6.5 na base real: o orçamento de cada mês fecha a conta (disponível − consumido =
restante; consumido = gastos − deduções) e a taxa de poupança do orçamento é a da lista v2 fixada
(ADR-016)."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import asyncpg
import pytest

from engines.closing import service as closing
from engines.common.dates import months_between
from scripts.ops.baseline import pinned_savings_v2
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_orcamento_na_base_real() -> None:
    import main  # noqa: F401

    pinned = pinned_savings_v2()
    if pinned is None:
        require_or_skip("lista v2 fixada ausente")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            for month in months_between(date(2024, 7, 1), date(2026, 9, 1)):
                b = await closing.month_budget(conn, month)
                key = f"{month:%Y-%m}"
                assert b.restante.value == b.disponivel.value - b.consumido.value, key
                assert b.consumido.value == (
                    b.gastos - b.deducao_fixos - b.deducao_dividas - b.devolucoes
                ), key
                expected = pinned.get(key)
                if expected is None:
                    assert b.taxa_poupanca.value is None, key
                else:
                    assert b.taxa_poupanca.value == Decimal(expected).quantize(Decimal("0.01")), key
        finally:
            await conn.close()
    finally:
        await restore_dados()
