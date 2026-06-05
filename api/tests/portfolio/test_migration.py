"""Tests for STORY-02-17-18 — parsing/import da migração de OPERAÇÕES (CSV)."""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.portfolio.migration import (
    import_operations,
    normalize_category,
    normalize_tipo,
    operation_hash,
    parse_operations_csv,
)

_CSV = """data,ticker,categoria,tipo,quantidade,preco_unitario,total
2024-07-15,PETR4F,ACOES,buy,18,32.11,577.98
2024-08-20,MXRF11,FII,income,1,5.00,5.00
2024-09-01,Flash_CDB,RENDA_FIXA,buy,,,12000.00
15/10/2024,BTC,CRIPTO,sell,0.001,200000.00,200.00
"""


class TestNormalizers:
    def test_category_mapping(self) -> None:
        assert normalize_category("ACOES") == "Ações Nacionais"
        assert normalize_category("etf") == "ETFs"
        assert normalize_category("FII") == "FIIs"
        assert normalize_category("RENDA_FIXA") == "Renda Fixa"
        assert normalize_category("APOSENTADORIA") == "Aposentadoria"
        assert normalize_category("cripto") == "Cripto"

    def test_tipo_mapping(self) -> None:
        assert normalize_tipo("buy") == "compra"
        assert normalize_tipo("sell") == "venda"
        assert normalize_tipo("income") == "dividendo"
        # pt-br passthrough
        assert normalize_tipo("aporte") == "aporte"
        assert normalize_tipo("juros") == "juros"

    def test_hash_is_stable_and_distinct(self) -> None:
        h1 = operation_hash(date(2024, 7, 15), "PETR4F", "compra", 577.98)
        h2 = operation_hash(date(2024, 7, 15), "PETR4F", "compra", 577.98)
        h3 = operation_hash(date(2024, 7, 15), "PETR4F", "venda", 577.98)
        assert h1 == h2
        assert h1 != h3


class TestParse:
    def test_parse_maps_columns(self) -> None:
        rows = parse_operations_csv(_CSV)
        assert len(rows) == 4
        petr = rows[0]
        assert petr["asset_symbol"] == "PETR4F"
        assert petr["asset_category"] == "Ações Nacionais"
        assert petr["tipo"] == "compra"
        assert petr["quantidade"] == 18.0
        assert abs(petr["valor_unitario"] - 32.11) < 0.001
        assert petr["data_operacao"] == date(2024, 7, 15)
        assert petr["external_id"]  # non-empty hash

    def test_income_maps_to_dividendo(self) -> None:
        rows = parse_operations_csv(_CSV)
        assert rows[1]["tipo"] == "dividendo"

    def test_renda_fixa_without_quantity(self) -> None:
        """RF sem quantidade → quantidade=1, valor_unitario=total."""
        rows = parse_operations_csv(_CSV)
        rf = rows[2]
        assert rf["asset_symbol"] == "Flash_CDB"
        assert rf["quantidade"] == 1.0
        assert abs(rf["valor_unitario"] - 12000.0) < 0.001

    def test_parses_br_date_format(self) -> None:
        rows = parse_operations_csv(_CSV)
        assert rows[3]["data_operacao"] == date(2024, 10, 15)


class TestImport:
    @pytest.mark.asyncio
    async def test_import_is_idempotent(
        self, pool: Any, portfolio_user: dict[str, Any]
    ) -> None:
        """Importar duas vezes não duplica (external_id hash)."""
        user_id = portfolio_user["user_id"]
        rows = parse_operations_csv(_CSV)
        async with pool.acquire() as conn:
            r1 = await import_operations(conn, user_id, rows)
            r2 = await import_operations(conn, user_id, rows)
            count = await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE user_id = $1", user_id
            )
        assert r1["imported"] == 4
        assert r1["skipped"] == 0
        assert r2["imported"] == 0
        assert r2["skipped"] == 4
        assert count == 4
