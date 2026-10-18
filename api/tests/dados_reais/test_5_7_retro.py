"""Story 5.7 — fechamento retroativo na base real: com os consolidados da B3 importados pelo
protocolo e os saldos da âncora gravados, `close_retro` fecha jul/2024–mai/2026 (23 meses, origin
retro); a taxa de poupança congelada de cada mês = a lista v2 fixada (gate de dados, ADR-016);
fev/2025 fica "retroativo divergente" (P8) e é listado; conferidos = jul/2024–jan/2025 (a
conferência é encadeada: depois do P8 o saldo calculado não bate); os meses com consolidado
(dez/2024, dez/2025, jan–mai/2026) são valorados por ele, os outros ficam "patrimônio não coberto";
cripto estimada; rodar de novo não cria versão."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal

import asyncpg
import pytest

from engines.ingest import service as ingest_service
from scripts.ops import close_retro
from scripts.ops.ancorar_saldo import FILES_DIR, anchor
from scripts.ops.baseline import pinned_savings_v2
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

START, END = date(2024, 7, 1), date(2026, 5, 1)
CONSOLIDADO = {date(2024, 12, 1), date(2025, 12, 1)} | {date(2026, m, 1) for m in range(1, 6)}


async def test_close_retro_base_real() -> None:
    import main  # noqa: F401

    pinned = pinned_savings_v2()
    files = sorted(close_retro.CONSOLIDADOS_DIR.rglob("*.xlsx"))
    if pinned is None or not files:
        require_or_skip("lista v2 fixada ou consolidados ausentes")
        raise AssertionError("inalcançável")
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            with pytest.raises(close_retro.RetroAborted, match="Consolidado B3 não importado"):
                await close_retro.run(conn, START, END)
            preview = await ingest_service.preview(conn, [(p.name, p.read_bytes()) for p in files])
            await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            await anchor(conn, sorted(FILES_DIR.rglob("*.ofx")), write=True)
            said: list[str] = []
            report = await close_retro.run(conn, START, END, echo=said.append)
            assert len(report.closed) == 23 and not report.blocked, report.blocked
            assert report.divergent == [date(2025, 2, 1)]
            rows = await conn.fetch(
                "SELECT c.month, c.origin, c.coverage, t.taxa_poupanca, t.saldo_conferido "
                "FROM month_closes c JOIN month_summary_totals t USING (month, version) "
                "ORDER BY c.month"
            )
            assert [r["month"] for r in rows] == report.closed
            for r in rows:
                key = f"{r['month']:%Y-%m}"
                assert r["origin"] == "retro"
                expected = pinned.get(key)
                got = r["taxa_poupanca"]
                if expected is None:
                    assert got is None, key
                else:
                    assert got == Decimal(expected).quantize(Decimal("0.01")), key
                coverage = json.loads(r["coverage"])
                if r["month"] in CONSOLIDADO:
                    assert coverage["B3"].startswith("consolidado de "), key
                else:
                    assert coverage["B3"] == "patrimônio não coberto", key
                # sem histórico de carteira: estimada pelo aplicado; antes de qualquer cripto, o
                # bloco é zero de verdade (revisão do Épico 8)
                assert coverage["cripto"].startswith("estimada") or coverage["cripto"] == (
                    "sem cripto"
                ), key
            conferidos = [r["month"] for r in rows if r["saldo_conferido"]]
            assert conferidos == [m for m in report.closed if m < date(2025, 2, 1)]
            again = await close_retro.run(conn, START, END, echo=said.append)
            assert again.closed == [] and len(again.skipped) == 23
            assert await conn.fetchval("SELECT count(*) FROM month_closes") == 23
        finally:
            await conn.close()
    finally:
        await restore_dados()


async def test_refechar_completa_orcamento_base_real() -> None:
    """Story 6.8 na base real: os meses retroativos fechados antes do orçamento (termos nulos
    `fora_do_resumo`, como estão no banco local) ganham, pelo `refechar --completar`, a versão 2
    com o orçamento; a taxa de poupança congelada não muda e a conta fecha."""
    import main  # noqa: F401
    from scripts.ops import refechar

    files = sorted(close_retro.CONSOLIDADOS_DIR.rglob("*.xlsx"))
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            preview = await ingest_service.preview(conn, [(p.name, p.read_bytes()) for p in files])
            await ingest_service.confirm(conn, preview.batch_id, preview.hash)
            await anchor(conn, sorted(FILES_DIR.rglob("*.ofx")), write=True)
            await close_retro.run(conn, START, END, echo=lambda _: None)
            terms = (
                "consumido",
                "disponivel",
                "restante",
                "restante_sem_resgates",
                "consumo_financiado",
            )
            await conn.execute(
                f"UPDATE month_summary_totals SET {', '.join(f'{t} = NULL' for t in terms)}, "
                "unavailable = unavailable || $1::jsonb",
                json.dumps({t: "fora_do_resumo" for t in terms}),
            )
            await conn.execute("DELETE FROM month_plans")
            before = {
                r["month"]: r["taxa_poupanca"]
                for r in await conn.fetch("SELECT month, taxa_poupanca FROM month_summary_totals")
            }
            done = await refechar.run(
                conn, refechar.parse_months("2024-07..2026-05"), echo=lambda _: None
            )
            assert len(done) == 23 and {v for _, v in done} == {2}
            rows = await conn.fetch(
                "SELECT * FROM month_summary_totals WHERE version = 2 ORDER BY month"
            )
            for r in rows:
                key = f"{r['month']:%Y-%m}"
                assert all(r[t] is not None for t in terms), key
                assert r["restante"] == r["disponivel"] - r["consumido"], key
                assert r["taxa_poupanca"] == before[r["month"]], key
                assert json.loads(r["unavailable"])["aporte_planejado"] == "nao_definido", key
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM month_plans WHERE aporte_planejado IS NULL"
                )
                == 23
            )
        finally:
            await conn.close()
    finally:
        await restore_dados()
