"""Story 2.6 — revisão 0021 (resgates como receita, faturas → Cartão de crédito, Repasse →
Devoluções, par investimento ↔ resgate) sobre a base real.

restaura → `upgrade 0020` → mede → `upgrade 0021` → mede:
- mês x categoria: só os deltas listados (resgates, as 18 faturas);
- trânsito, bloco cripto e caixinhas lidos pelas duas keys = antes (por key, sem par);
- XIRR, aplicado e net = baseline; `asset_operations` intactas;
- eventos `migration` = linhas movidas; idempotente;
- taxa de poupança v2 (`ledger/calc`) só difere da v1 nos meses com Repasse, Reembolso ou entrada
  a classificar, e é igual à lista v2 fixada (ADR-016).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from engines.ledger.service import monthly_savings
from engines.portfolio import transit
from engines.portfolio.caixinhas import CAIXINHAS, CDB_GUANABARA, build_caixinha_ops
from engines.portfolio.crypto_sleeve import sleeve_cashflows
from scripts._common import resolve_owner
from scripts.ops.baseline import compute_baseline, load_pinned_baseline, pinned_savings_v2
from scripts.ops.compare_categorias import LABEL_BY_ID, diff, snapshot
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import API_DIR, alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

TRILHOS_TRANSIT = {
    "B3 (corretoras)": ("invest:toro_b3",),
    "Tesouro Direto": ("invest:tesouro_nubank",),
    "Renda Fixa Nubank": ("invest:caixinha_rdb", "invest:renda_fixa_nubank"),
    "Debêntures Flash": ("invest:debentures_flash",),
}
CRYPTO = ("invest:binance", "invest:cripto_diversos", "invest:cripto_nubank", "invest:liquid_defi")
EXPECTED_LABEL = """
    CASE
      WHEN c.key LIKE 'invest:%' AND t.amount > 0 THEN 'Resgate ' || CASE c.key
        WHEN 'invest:caixinha_rdb' THEN 'Caixinha/RDB Nubank'
        WHEN 'invest:toro_b3' THEN 'Toro (B3)'
        WHEN 'invest:tesouro_nubank' THEN 'Tesouro Direto Nubank'
        WHEN 'invest:renda_fixa_nubank' THEN 'Renda Fixa Nubank'
        WHEN 'invest:cripto_nubank' THEN 'Cripto Nubank'
        WHEN 'invest:cripto_diversos' THEN 'Cripto Diversos'
        WHEN 'invest:binance' THEN 'Binance'
        WHEN 'invest:debentures_flash' THEN 'Debêntures Flash'
        WHEN 'invest:liquid_defi' THEN 'Liquid/DeFi' END
      WHEN c.key = 'gasto:dividas' AND t.description ILIKE '%fatura%'
           AND t.date < '2025-12-01' THEN 'Cartão de crédito'
      ELSE c.name END
"""


async def _by_keys(conn: asyncpg.Connection, keys: tuple[str, ...]) -> list[Any]:
    return await conn.fetch(
        "SELECT t.date, t.amount, t.external_id, t.description FROM transactions t "
        "JOIN categories c ON c.id = t.category_id WHERE c.key = ANY($1) ORDER BY t.date, t.id",
        list(keys),
    )


async def _readers_before(conn: asyncpg.Connection) -> dict[str, Any]:
    """Como os leitores eram na 0020: por key do investimento, sem par (o resgate ainda estava
    na subcategoria de investimento)."""
    saiu = {
        rail: round(-float(sum((r["amount"] for r in await _by_keys(conn, keys)), Decimal(0))), 2)
        for rail, keys in TRILHOS_TRANSIT.items()
    }
    flows = sorted((r["date"], float(r["amount"])) for r in await _by_keys(conn, CRYPTO))
    caixinhas = {}
    for spec in (*CAIXINHAS, CDB_GUANABARA):
        rows = [
            r
            for r in await _by_keys(conn, spec.source_keys)
            if spec.desc_match
            and any(d.lower() in (r["description"] or "").lower() for d in spec.desc_match)
            and r["amount"] != 0
        ]
        caixinhas[spec.symbol] = sorted(
            (f"caixinha:{spec.symbol}:{r['external_id']}", float(abs(r["amount"]))) for r in rows
        )
    return {"saiu": saiu, "sleeve_flows": flows, "caixinhas": caixinhas}


async def readers_now(conn: asyncpg.Connection) -> dict[str, Any]:
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


async def _ops_digest(conn: asyncpg.Connection) -> Any:
    return await conn.fetchrow(
        "SELECT count(*), sum(quantidade * valor_unitario), "
        "string_agg(external_id, ',' ORDER BY external_id) FROM asset_operations"
    )


def _downgrade(dsn: str, rev: str) -> None:
    import os

    subprocess.run(
        ["alembic", "downgrade", rev],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": dsn},
        check=True,
    )


async def test_reclassificacoes() -> None:
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0020_categorize_chokepoint")
        conn = await asyncpg.connect(dsn)
        try:
            expected = await snapshot(
                conn, f"(SELECT {EXPECTED_LABEL} FROM categories c WHERE c.id = t.category_id)"
            )
            readers_before = await _readers_before(conn)
            ops_before = await _ops_digest(conn)
            moved = await conn.fetchval(
                "SELECT count(*) FROM transactions t JOIN categories c ON c.id = t.category_id "
                "WHERE (c.key LIKE 'invest:%' AND t.amount > 0) OR (c.key = 'gasto:dividas' "
                "AND t.description ILIKE '%fatura%' AND t.date < '2025-12-01')"
            )
            faturas_assinaturas = await conn.fetchval(
                "SELECT count(*) FROM transactions t JOIN categories c ON c.id = t.category_id "
                "WHERE c.key = 'gasto:assinaturas' AND t.description ILIKE '%fatura%'"
            )
            v1 = {
                r["m"]: r["savings_rate"]
                for r in await conn.fetch(
                    "SELECT month::date AS m, savings_rate FROM monthly_summary ORDER BY 1"
                )
            }
            changing = {
                r["m"]
                for r in await conn.fetch(
                    "SELECT DISTINCT date_trunc('month', t.date)::date AS m FROM transactions t "
                    "JOIN categories c ON c.id = t.category_id WHERE c.key IN "
                    "('trabalho:repasse', 'devolucao:reembolso', 'sistema:entrada_a_classificar')"
                )
            }
        finally:
            await conn.close()

        await asyncio.to_thread(alembic_upgrade, dsn, "0021_reclassificacoes")

        conn = await asyncpg.connect(dsn)
        try:
            assert diff(expected, await snapshot(conn, LABEL_BY_ID)) == {}
            assert moved > 0
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM categorization_events WHERE cause = 'migration'"
                )
                == moved
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM transactions t JOIN categories c ON c.id = t.category_id "
                    "WHERE c.key = 'gasto:cartao_credito'"
                )
                == 18
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM transactions t JOIN categories c ON c.id = t.category_id "
                    "WHERE c.key = 'gasto:assinaturas' AND t.description ILIKE '%fatura%'"
                )
                == faturas_assinaturas
                == 4
            )
            assert (
                await conn.fetchval(
                    "SELECT g.key || '/' || c.role FROM categories c "
                    "JOIN category_groups g ON g.id = c.group_id WHERE c.key = 'trabalho:repasse'"
                )
                == "devolucoes/devolucao"
            )
            pairs = dict(
                await conn.fetch(
                    "SELECT key, pair_key FROM categories WHERE key LIKE 'invest:%' "
                    "OR key LIKE 'resgate:%'"
                )
            )
            assert all(pairs[k] and pairs[pairs[k]] == k for k in pairs)
            assert await readers_now(conn) == readers_before
            assert await _ops_digest(conn) == ops_before
            # XIRR, aplicado e net = baseline
            base = load_pinned_baseline()
            if base is None:
                require_or_skip("baseline fixado não encontrado")
                raise AssertionError("inalcançável")
            got = json.loads(
                json.dumps(
                    await compute_baseline(conn, date.fromisoformat(base["evaluation_date"]))
                )
            )
            for k in ("xirr", "aplicado", "net", "counts"):
                assert got[k] == base[k], k
            # poupança v2: só muda onde há Repasse, Reembolso ou entrada a classificar
            v2 = await monthly_savings(conn)
            differ = {
                m
                for m, rate in v2.items()
                if v1.get(m) is None
                or rate is None
                or abs(Decimal(str(v1[m])) - rate * 100) > Decimal("0.0000001")
            }
            assert differ <= changing, sorted(differ - changing)
            pinned = pinned_savings_v2()
            if pinned is None:
                require_or_skip("lista v2 de poupança não fixada")
            assert {m.isoformat()[:7]: _fmt(r) for m, r in v2.items()} == pinned
        finally:
            await conn.close()

        # idempotência: reaplicar não acha nada a mudar
        await asyncio.to_thread(_downgrade, dsn, "0020_categorize_chokepoint")
        await asyncio.to_thread(alembic_upgrade, dsn, "0021_reclassificacoes")
        conn = await asyncpg.connect(dsn)
        try:
            assert diff(expected, await snapshot(conn, LABEL_BY_ID)) == {}
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM categorization_events WHERE cause = 'migration'"
                )
                == moved
            )
        finally:
            await conn.close()
    finally:
        await restore_dados()


def _fmt(rate: Decimal | None) -> str | None:
    return None if rate is None else str(round(rate * 100, 6))
