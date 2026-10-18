"""Story 3.5 — revisão 0025 sobre a base real: operação de caixinha ligada à transação e curadoria
protegida; depois de reimportar os OFX de 2024–2026 pelo protocolo (o hook do lote deriva as
caixinhas) e de rederivar tudo, net, aplicado e XIRR de cada caixinha/CDB = baseline."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import asyncpg
import pytest

from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.portfolio.caixinhas import CAIXINHAS, CDB_GUANABARA, derive_caixinha_ops
from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import API_DIR, alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

OFX_DIR = API_DIR.parent / "files" / "nubank"
SYMBOLS = {*(s.symbol for s in CAIXINHAS), CDB_GUANABARA.symbol, "Nubank-Encerradas"}


def _ofx_files() -> list[Path]:
    return sorted(p for year in ("2024", "2025", "2026") for p in (OFX_DIR / year).glob("*.ofx"))


async def test_caixinhas_ligadas_e_protegidas() -> None:
    import main  # noqa: F401 — adapters e hooks

    base = load_pinned_baseline()
    files = _ofx_files()
    if base is None or not files:
        require_or_skip("baseline fixado ou OFX de 2024–2026 ausentes")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM asset_operations WHERE external_id LIKE 'caixinha:%' "
                    "AND transaction_id IS NULL AND NOT protected"
                )
                == 0
            )
            protected = {
                (r["asset_symbol"], r["tipo"])
                for r in await conn.fetch(
                    "SELECT asset_symbol, tipo FROM asset_operations WHERE protected"
                )
            }
            assert protected == {
                ("Nubank-Turbo", "juros"),
                ("Nubank-Turbo", "resgate"),
                ("Nubank-Encerradas", "juros"),
                ("Flash-Debênture", "aporte"),  # 0040 (Story 7.6): integralizações ligadas
            }
            new = {}
            for path in files:
                preview = await ingest_service.preview(conn, [(path.name, path.read_bytes())])
                plan = preview.files[0]
                assert plan.error is None, (path.name, plan.error)
                new[path.name] = plan.new
                await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            assert sum(new.values()) == 0, {k: v for k, v in new.items() if v}
            again = await derive_caixinha_ops(conn, await get_owner_id(conn))
            assert again == {"created": 0, "updated": 0, "deleted": 0}
            # Story 7.5: toda transação ligada a uma operação tem o ativo dela (0039 + resolver);
            # sem operação, só a caixinha encerrada aponta para um ativo (o bucket)
            mismatch = await conn.fetchval(
                "SELECT count(*) FROM transactions t LEFT JOIN asset_operations o "
                "ON o.transaction_id = t.id LEFT JOIN assets a ON a.id = t.asset_id "
                "WHERE (o.id IS NOT NULL AND o.asset_id IS NOT NULL "
                "AND t.asset_id IS DISTINCT FROM o.asset_id) OR (o.id IS NULL AND t.asset_id "
                "IS NOT NULL AND a.price_ref <> 'Nubank-Encerradas')"
            )
            assert mismatch == 0
            encerradas = await conn.fetchval(
                "SELECT count(*) FROM transactions t JOIN assets a ON a.id = t.asset_id "
                "WHERE a.price_ref = 'Nubank-Encerradas'"
            )
            assert encerradas > 0  # as caixinhas encerradas vão para o bucket, como hoje
            got = json.loads(
                json.dumps(
                    await compute_baseline(conn, date.fromisoformat(base["evaluation_date"]))
                )
            )
        finally:
            await conn.close()
        for sym in SYMBOLS:
            for k in ("aplicado", "net"):
                assert got[k].get(sym) == base[k].get(sym), (k, sym)
            assert got["xirr"]["by_asset"].get(sym) == base["xirr"]["by_asset"].get(sym), sym
        assert got["xirr"]["consolidated"] == base["xirr"]["consolidated"]
    finally:
        await restore_dados()
