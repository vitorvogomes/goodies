"""Story 2.3 — revisão 0018 (grupos, roles, keys, category_id) sobre a base real.

restaura → mede (rótulo esperado com os deltas listados) → `alembic upgrade 0018` → mede
(subcategoria real). Deltas esperados: Flash Capital e Betuel → Recorrente (pagador preservado);
"Cripto Nubnak" → "Cripto Nubank"; "outros" importado sem revisão (ADR-016) → "a classificar".
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import asyncpg
import pytest

from engines.portfolio import transit
from engines.portfolio.caixinhas import CAIXINHAS, CDB_GUANABARA, build_caixinha_ops
from engines.portfolio.crypto_sleeve import sleeve_cashflows
from scripts._common import resolve_owner
from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from scripts.ops.compare_categorias import LABEL_BY_ID, diff, snapshot, total
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

REV = "0018_category_groups"
CUTOFF = "'2026-10-18 06:07:00+00'"
EXPECTED_LABEL = f"""
    CASE
      WHEN t.category IN ('Flash Capital', 'Betuel') AND t.kind = 'income' THEN 'Recorrente'
      WHEN t.category = 'Cripto Nubnak' THEN 'Cripto Nubank'
      WHEN t.category = 'outros' AND t.kind = 'income' THEN 'Entrada a classificar'
      WHEN t.category = 'outros' AND t.created_at >= {CUTOFF} THEN 'Saída a classificar'
      ELSE t.category END
"""


_LEGACY_RAILS = {
    "B3 (corretoras)": ("Toro (B3)",),
    "Tesouro Direto": ("Tesouro Direto Nubank",),
    "Renda Fixa Nubank": ("Caixinha/RDB Nubank", "Renda Fixa Nubank"),
    "Debêntures Flash": ("Flash Capital debêntures",),
}
_LEGACY_CRYPTO = ("Binance", "Cripto Diversos", "Cripto Nubnak", "Liquid/DeFi")
_LEGACY_CAIXINHA = {
    "Nubank-SnowTrip": ("Caixinha/RDB Nubank",),
    "Nubank-Turbo": ("Caixinha/RDB Nubank",),
    "Nubank-Reserva": ("Caixinha/RDB Nubank",),
    "Nubank-HotCash": ("Caixinha/RDB Nubank",),
    "Guanabara-CDB": ("Renda Fixa Nubank",),
}


async def _legacy_readers(conn: asyncpg.Connection) -> dict[str, Any]:
    """Definição v1 (por NOME) do que os leitores por key devem continuar devolvendo."""
    saiu = {}
    for rail, names in _LEGACY_RAILS.items():
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions "
            "WHERE kind = 'investment' AND category = ANY($1)",
            list(names),
        )
        saiu[rail] = round(-float(val), 2)
    flows = await conn.fetch(
        "SELECT date, amount FROM transactions WHERE category = ANY($1) ORDER BY date, amount",
        list(_LEGACY_CRYPTO),
    )
    caixinhas = {}
    for spec in (*CAIXINHAS, CDB_GUANABARA):
        if not spec.desc_match:
            caixinhas[spec.symbol] = []
            continue
        rows = await conn.fetch(
            "SELECT external_id, abs(amount) q FROM transactions WHERE category = ANY($1) AND "
            "EXISTS (SELECT 1 FROM unnest($2::text[]) d WHERE description ILIKE '%' || d || '%') "
            "AND amount <> 0",
            list(_LEGACY_CAIXINHA[spec.symbol]),
            list(spec.desc_match),
        )
        caixinhas[spec.symbol] = sorted(
            (f"caixinha:{spec.symbol}:{r['external_id']}", float(r["q"])) for r in rows
        )
    return {
        "saiu": saiu,
        "sleeve_flows": sorted((r["date"], float(r["amount"])) for r in flows),
        "caixinhas": caixinhas,
    }


async def _readers(conn: asyncpg.Connection) -> dict[str, Any]:
    """Os mesmos números pelos leitores por key (código da v2)."""
    uid = str((await resolve_owner(conn))["id"])
    rails = (await transit.calculate_transit(conn, uid))["rails"]
    caixinhas = {}
    for spec in (*CAIXINHAS, CDB_GUANABARA):
        ops = await build_caixinha_ops(conn, spec)
        caixinhas[spec.symbol] = sorted((o["external_id"], o["quantidade"]) for o in ops)
    return {
        "saiu": {r["rail"]: r["saiu_brl"] for r in rails},
        "sleeve_flows": sorted(await sleeve_cashflows(conn)),
        "caixinhas": caixinhas,
    }


async def test_categorias_em_dois_niveis() -> None:
    dsn = await restore_dados()
    try:
        conn = await asyncpg.connect(dsn)
        try:
            expected = await snapshot(conn, EXPECTED_LABEL)
            raw_before = await snapshot(conn, "t.category")
            payers = await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE category IN ('Flash Capital', 'Betuel') "
                "AND kind = 'income'"
            )
            readers_before = await _legacy_readers(conn)
        finally:
            await conn.close()

        await asyncio.to_thread(alembic_upgrade, dsn, REV)

        conn = await asyncpg.connect(dsn)
        try:
            after = await snapshot(conn, LABEL_BY_ID)
            # só os deltas listados: o rótulo esperado bate par a par
            assert diff(expected, after) == {}
            assert total(after) == total(raw_before)  # contagem e soma intactas
            assert (
                await conn.fetchval("SELECT count(*) FROM transactions WHERE category_id IS NULL")
                == 0
            )
            assert (
                await conn.fetchval("SELECT count(*) FROM categories WHERE key LIKE 'custom:%'")
                == 0
            )
            # kind gravado = kind do grupo da subcategoria (nenhuma divergência na base real)
            divergent = await conn.fetch(
                "SELECT t.category, t.kind, g.kind gk, count(*) FROM transactions t "
                "JOIN categories c ON c.id = t.category_id "
                "JOIN category_groups g ON g.id = c.group_id "
                "WHERE t.kind <> g.kind GROUP BY 1, 2, 3"
            )
            assert [tuple(r) for r in divergent] == []
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM transactions WHERE payer IN ('Flash Capital', 'Betuel') "
                    "AND category = 'Recorrente'"
                )
                == payers
            )
            assert (
                await conn.fetchval("SELECT count(*) FROM fixed_costs WHERE category_id IS NULL")
                == 0
            )
            # poupança por mês (view v1, ainda válida na 0018) = baseline fixado (ADR-016)
            base = load_pinned_baseline()
            if base is None:
                require_or_skip("baseline fixado não encontrado")
                raise AssertionError("inalcançável")
            v1 = {
                r["m"]: None if r["s"] is None else str(round(r["s"], 6))
                for r in await conn.fetch(
                    "SELECT to_char(month, 'YYYY-MM') m, savings_rate s FROM monthly_summary"
                )
            }
            assert v1 == base["savings_rate"]
        finally:
            await conn.close()

        # Os leitores por key (com o par investimento ↔ resgate) são do código atual: medem a base
        # migrada até o head contra a definição legada por nome, e não mudam com renome.
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            assert await _readers(conn) == readers_before
            await conn.execute("UPDATE categories SET name = name || ' (renomeada)'")
            assert await _readers(conn) == readers_before
            await conn.execute("UPDATE categories SET name = replace(name, ' (renomeada)', '')")
            got = json.loads(
                json.dumps(
                    await compute_baseline(conn, date.fromisoformat(base["evaluation_date"]))
                )
            )
            for k in ("xirr", "aplicado", "net", "counts"):
                assert got[k] == base[k], k
        finally:
            await conn.close()
    finally:
        await restore_dados()
