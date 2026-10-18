"""Classes de ativo (AD-1/AD-11 — Story 3.2: saem de `portfolio/constants.py` para `common`).

SSOT das 6 categorias canônicas de ativo (§3.2 do débito técnico m2).

Antes, as strings ("Ações Nacionais", "ETFs", "FIIs", "Renda Fixa", "Aposentadoria",
"Cripto") estavam duplicadas em `targets.py`, `service._IR_ALIQUOTAS`, `migration.CATEGORY_MAP`,
`b3_import.b3_category` e `caixinhas._CATEGORY` — uma divergência de casing fazia a posição
sumir da alocação/IR silenciosamente. Agora todos importam daqui.

`StrEnum` (Python 3.12): cada membro COMPARA e HASHEIA igual à sua string → as linhas já
gravadas em `asset_operations.asset_category`/`portfolio_targets.category` continuam casando
sem nenhuma migração de dados.

Os frozensets de roteamento dizem qual fetcher do Market Engine (m3) cota cada categoria.
Renda Fixa fica de fora (preço `is_manual`: Flash/caixinhas/CDB — ver caixinhas.py).
"""

from __future__ import annotations

from enum import StrEnum


class AssetCategory(StrEnum):
    """Categoria canônica de um ativo do portfólio."""

    ACOES = "Ações Nacionais"
    ETFS = "ETFs"
    FIIS = "FIIs"
    RENDA_FIXA = "Renda Fixa"
    APOSENTADORIA = "Aposentadoria"
    CRIPTO = "Cripto"


# Todas as categorias canônicas (como strings, para checagens de pertencimento).
CATEGORIES: frozenset[str] = frozenset(c.value for c in AssetCategory)

# Roteamento categoria -> fetcher (m3). Renda Fixa é deliberadamente omitida (is_manual).
B3_CATEGORIES: frozenset[str] = frozenset(
    {AssetCategory.ACOES, AssetCategory.ETFS, AssetCategory.FIIS}
)
CRYPTO_CATEGORIES: frozenset[str] = frozenset({AssetCategory.CRIPTO})
TREASURY_CATEGORIES: frozenset[str] = frozenset({AssetCategory.APOSENTADORIA})


class AssetClass(StrEnum):
    """Classe do ativo no modelo v2 (AD-11): `assets.class` e `portfolio_targets.class`."""

    ACOES_BR = "acoes_br"
    ETFS = "etfs"
    FIIS = "fiis"
    RENDA_FIXA = "renda_fixa"
    APOSENTADORIA = "aposentadoria"
    CRIPTO = "cripto"


# Rótulo legado (asset_operations.asset_category, portfolio_targets.category) → classe v2. É o mesmo
# mapa de `goodies_asset_class()` da revisão 0023.
CLASS_BY_CATEGORY: dict[str, AssetClass] = {
    AssetCategory.ACOES: AssetClass.ACOES_BR,
    AssetCategory.ETFS: AssetClass.ETFS,
    AssetCategory.FIIS: AssetClass.FIIS,
    AssetCategory.RENDA_FIXA: AssetClass.RENDA_FIXA,
    AssetCategory.APOSENTADORIA: AssetClass.APOSENTADORIA,
    AssetCategory.CRIPTO: AssetClass.CRIPTO,
}


def canonical_category(label: str) -> str:
    """Rótulo de classe sem diferença de caixa → o canônico; fora das 6 classes → ValueError."""
    wanted = label.strip().lower()
    for category in AssetCategory:
        if category.value.lower() == wanted:
            return category.value
    raise ValueError(f"categoria deve ser uma de {sorted(CATEGORIES)}")
