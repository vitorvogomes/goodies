"""SSOT das 6 categorias canônicas de ativo (§3.2 do débito técnico m2).

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
