"""SSOT de categorias (§3.2 do débito m2): trava o casing e a consistência entre
os consumidores (targets, migration, b3_import) para que uma divergência de string
nunca faça uma posição sumir da alocação/IR sem erro.

Testes puros (sem DB/Redis).
"""
from __future__ import annotations

from engines.portfolio.b3_import import b3_category
from engines.portfolio.constants import (
    B3_CATEGORIES,
    CATEGORIES,
    CRYPTO_CATEGORIES,
    TREASURY_CATEGORIES,
    AssetCategory,
)
from engines.portfolio.migration import CATEGORY_MAP
from engines.portfolio.targets import PORTFOLIO_TARGETS


def test_six_canonical_categories_exact_casing() -> None:
    assert {c.value for c in AssetCategory} == {
        "Ações Nacionais",
        "ETFs",
        "FIIs",
        "Renda Fixa",
        "Aposentadoria",
        "Cripto",
    }


def test_strenum_compares_equal_to_string() -> None:
    # zero migração de dados: o membro do enum == a string gravada no Postgres
    assert AssetCategory.ACOES == "Ações Nacionais"
    assert "Renda Fixa" in CATEGORIES


def test_targets_use_canonical_categories() -> None:
    assert {t["category"] for t in PORTFOLIO_TARGETS} == set(CATEGORIES)


def test_category_map_values_are_canonical() -> None:
    for value in CATEGORY_MAP.values():
        assert value in CATEGORIES, value


def test_b3_category_outputs_are_canonical() -> None:
    for ticker in [
        "PETR4",
        "NASD11",
        "MXRF11",
        "Tesouro IPCA+ 2040",
        "XPTO99",  # desconhecido -> fallback ação
        "ZZZZ11",  # desconhecido em 11 -> fallback FII
    ]:
        assert b3_category(ticker) in CATEGORIES


def test_routing_sets_are_canonical_subsets() -> None:
    assert B3_CATEGORIES <= CATEGORIES
    assert CRYPTO_CATEGORIES <= CATEGORIES
    assert TREASURY_CATEGORIES <= CATEGORIES
    # Renda Fixa não é cotável por fetcher de mercado (preço is_manual)
    market_fetchable = B3_CATEGORIES | CRYPTO_CATEGORIES | TREASURY_CATEGORIES
    assert AssetCategory.RENDA_FIXA not in market_fetchable
