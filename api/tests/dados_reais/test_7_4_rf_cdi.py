"""Story 7.4 na base real: a revisão 0038 cadastra o %CDI das caixinhas e do CDB (Snow Trip e
Reserva 100, Turbo 115, Guanabara 117,5), libera o preço deles para o job `rf_cdi` (não manual) e
não muda nenhum valor: o XIRR/aplicado/net do baseline da Story 1.3 continuam iguais."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal

import asyncpg
import pytest

from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_rf_cdi_cadastrado_sem_mudar_valor() -> None:
    import main  # noqa: F401

    base = load_pinned_baseline()
    if base is None:
        require_or_skip("baseline fixado ausente")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            rows = {
                r["key"]: r["pct_cdi"]
                for r in await conn.fetch("SELECT key, pct_cdi FROM assets WHERE valuation = 'cdi'")
            }
            assert rows == {
                "caixinha:snowtrip": Decimal("100.00"),
                "caixinha:turbo": Decimal("115.00"),
                "caixinha:reserva": Decimal("100.00"),
                "cdb:guanabara": Decimal("117.50"),
            }
            manual = await conn.fetchval(
                "SELECT count(*) FROM asset_prices p JOIN assets a ON a.price_ref = p.ticker "
                "WHERE a.valuation = 'cdi' AND p.is_manual"
            )
            assert manual == 0
            got = json.loads(
                json.dumps(
                    await compute_baseline(conn, date.fromisoformat(base["evaluation_date"]))
                )
            )
        finally:
            await conn.close()
        for k in ("xirr", "aplicado", "net"):
            assert got[k] == base[k], k
    finally:
        await restore_dados()
