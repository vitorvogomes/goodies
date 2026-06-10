"""A3 — import_b3_workbook: orquestração + regra de cobertura (DB-backed).

A regra de cobertura é a defesa contra a dupla contagem trade-vs-liquidação: o hash
não protege (datas diferentes entre fontes), só a cobertura por proveniência.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.portfolio import service
from engines.portfolio.b3_import_service import import_b3_workbook

_NEG_HEADER = (
    "Data do Negócio", "Tipo de Movimentação", "Mercado", "Prazo/Vencimento",
    "Instituição", "Código de Negociação", "Quantidade", "Preço", "Valor",
)


def _neg_sheet(rows: list[tuple[Any, ...]]) -> dict[str, list[tuple[Any, ...]]]:
    return {"Negociação": [_NEG_HEADER, *rows]}


async def _count_ops(pool: Any, uid: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM asset_operations WHERE user_id = $1", uid
        )


async def _seed_op(
    pool: Any, uid: str, broker: str, sym: str, cat: str, d: date, ext: str
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
            "asset_category, tipo, quantidade, valor_unitario, data_operacao, "
            "external_id) VALUES ($1,$2,$3,$4,'compra',1,10.0,$5,$6)",
            uid, broker, sym, cat, d, ext,
        )


class TestDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_write(self, pool: Any, portfolio_user: dict) -> None:
        uid = portfolio_user["user_id"]
        sheets = _neg_sheet(
            [("05/06/2026", "Compra", "Frac", "-", "SANT", "BBAS3F", 3, 19.46, 58.38)]
        )
        before = await _count_ops(pool, uid)
        async with pool.acquire() as conn:
            rep = await import_b3_workbook(conn, uid, sheets, dry_run=True)
        assert rep["imported"] == 1  # a importar
        assert rep["dry_run"] is True
        assert await _count_ops(pool, uid) == before  # nada gravado


class TestCoverage:
    @pytest.mark.asyncio
    async def test_skips_dates_covered_by_other_provenance(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        """ARMADILHA: maio já na base (Toro/B3, data de liquidação). A negociação
        maio->junho importa só a cauda de junho; maio vira overlap (sem dobrar)."""
        uid = portfolio_user["user_id"]
        await _seed_op(
            pool, uid, "Toro/B3", "BBAS3", "Ações Nacionais",
            date(2026, 5, 20), "legacy-bbas3-mai",
        )
        sheets = _neg_sheet([
            ("15/05/2026", "Compra", "Frac", "-", "SANT", "BBAS3F", 2, 19.0, 38.0),
            ("05/06/2026", "Compra", "Frac", "-", "SANT", "BBAS3F", 3, 19.46, 58.38),
        ])
        async with pool.acquire() as conn:
            rep = await import_b3_workbook(conn, uid, sheets, dry_run=False)
        assert rep["imported"] == 1
        assert rep["skipped_overlap"] == 1
        assert rep["overlap_tickers"] == ["BBAS3"]
        assert await _count_ops(pool, uid) == 2  # legada + junho

    @pytest.mark.asyncio
    async def test_new_ticker_flagged(self, pool: Any, portfolio_user: dict) -> None:
        uid = portfolio_user["user_id"]
        sheets = _neg_sheet(
            [("05/06/2026", "Compra", "Vista", "-", "SANT", "WEGE3", 1, 50.0, 50.0)]
        )
        async with pool.acquire() as conn:
            rep = await import_b3_workbook(conn, uid, sheets, dry_run=True)
        assert "WEGE3" in rep["new_tickers"]

    @pytest.mark.asyncio
    async def test_idempotent_reimport(self, pool: Any, portfolio_user: dict) -> None:
        uid = portfolio_user["user_id"]
        sheets = _neg_sheet(
            [("05/06/2026", "Compra", "Frac", "-", "SANT", "BBAS3F", 3, 19.46, 58.38)]
        )
        async with pool.acquire() as conn:
            r1 = await import_b3_workbook(conn, uid, sheets, dry_run=False)
            r2 = await import_b3_workbook(conn, uid, sheets, dry_run=False)
        assert r1["imported"] == 1
        assert r2["imported"] == 0
        assert r2["skipped_duplicate"] == 1


class TestConsolidado:
    @pytest.mark.asyncio
    async def test_upserts_prices_respecting_manual(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await service.upsert_price(
                conn, "PETR4", 99.99, source="manual", is_manual=True
            )
        sheets = {
            "Posição - Ações": [
                ("Código de Negociação", "Preço de Fechamento"),
                ("PETR4", 30.0),
                ("BBAS3", 20.3),
            ],
        }
        async with pool.acquire() as conn:
            rep = await import_b3_workbook(conn, uid, sheets, dry_run=False)
        assert rep["file_type"] == "consolidado"
        # achado C4: PETR4 era manual e foi PULADA (precedência is_manual) -> o contador
        # conta só o que realmente gravou (antes contava len(prices), inflando)
        assert rep["prices_upserted"] == 1
        assert rep["prices_skipped_manual"] == 1
        async with pool.acquire() as conn:
            petr = await conn.fetchval(
                "SELECT price_brl FROM asset_prices WHERE ticker = 'PETR4'"
            )
            bbas = await conn.fetchval(
                "SELECT price_brl FROM asset_prices WHERE ticker = 'BBAS3'"
            )
        assert abs(float(petr) - 99.99) < 0.01  # manual preservado
        assert abs(float(bbas) - 20.3) < 0.01
