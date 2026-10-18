"""Story 3.8 — os arquivos reais de `files/b3/` pelo protocolo sobre a base atual: 0 operações novas
(a base já cobre até 16/10/2026; a liquidação D+2 de 09/06/2026 casa com os negócios de 05/06),
consolidados viram snapshots com a data do nome e, com os mesmos preços, o XIRR B3+TD não muda
(= baseline)."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import asyncpg
import pytest

from engines.ingest import service as ingest_service
from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import API_DIR, alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

B3_DIR = API_DIR.parent / "files" / "b3"


async def test_arquivos_b3_reais() -> None:
    import main  # noqa: F401

    base = load_pinned_baseline()
    # P20: o relatório de negociação não é mais importado (só movimentação e consolidado)
    all_files = sorted(B3_DIR.rglob("*.xlsx"))
    files = [p for p in all_files if not p.name.startswith("negociacao")]
    refused = [p for p in all_files if p.name.startswith("negociacao")]
    if base is None or not files:
        require_or_skip("baseline fixado ou arquivos B3 ausentes")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            if refused:
                negociacao = await ingest_service.preview(
                    conn, [(p.name, p.read_bytes()) for p in refused]
                )
                assert all(f.error and "negociação" in f.error for f in negociacao.files)
            preview = await ingest_service.preview(conn, [(p.name, p.read_bytes()) for p in files])
            by_name = {f.file_name: f for f in preview.files}
            assert all(f.error is None and not f.needs for f in preview.files), [
                (f.file_name, f.error, f.needs) for f in preview.files if f.error or f.needs
            ]
            ops_new = {
                n: f.new for n, f in by_name.items() if f.source != "b3_consolidado" and f.new
            }
            assert ops_new == {}, ops_new
            anual = by_name["relatorio-consolidado-anual-2025.xlsx"]
            assert (anual.source, anual.period_end) == ("b3_consolidado", date(2025, 12, 31))
            setembro = by_name["relatorio-consolidado-mensal-2026-setembro.xlsx"]
            assert setembro.period_end == date(2026, 9, 30)
            # Preço do consolidado é outra conversa (muda a valoração de propósito): o invariante
            # aqui é das operações, então o XIRR é medido com os preços de antes.
            prices = await conn.fetch("SELECT * FROM asset_prices")
            await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            latest = await conn.fetchval("SELECT max(ref_date) FROM broker_position_snapshots")
            assert latest == date(2026, 9, 30)
            await conn.execute("DELETE FROM asset_prices")
            await conn.copy_records_to_table(
                "asset_prices", records=[tuple(r) for r in prices], columns=list(prices[0].keys())
            )
            snapshots = await conn.fetchval(
                "SELECT count(DISTINCT ref_date) FROM broker_position_snapshots"
            )
            consolidados = sum(1 for f in preview.files if f.source == "b3_consolidado")
            assert snapshots == consolidados
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
