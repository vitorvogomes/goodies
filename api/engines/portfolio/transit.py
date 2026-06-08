"""Reconciliação de trânsito (Pilar 2): "quanto saiu do Nubank vs quanto virou posição".

Por trilho de investimento: o ledger registra o que SAIU do Nubank (kind=investment, por
categoria); o `asset_operations` registra o que VIROU POSIÇÃO (custo líquido de compras -
vendas). O delta = "em trânsito" - dinheiro mandado que ainda não virou posição (ex.: a B3
publica o relatório com atraso). Mapa validado em 2026-06-07 (ver memória
`ledger-reconciliation-map`).

Cripto NÃO é trânsito (as carteiras são escaneadas ao vivo): reconcilia pelo sleeve
(investido vs valor atual), exposto à parte para não confundir perda com trânsito.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg


@dataclass(frozen=True)
class Rail:
    name: str
    ledger_categories: tuple[str, ...]  # categorias do ledger (kind=investment)
    asset_categories: tuple[str, ...]  # categorias em asset_operations
    asset_brokers: tuple[str, ...] | None  # None = qualquer broker


# Trilhos não-cripto. asset_brokers desambigua RF Nubank x Flash (mesma categoria).
RAILS: tuple[Rail, ...] = (
    Rail(
        "B3 (corretoras)",
        ("Toro (B3)",),
        ("Ações Nacionais", "ETFs", "FIIs"),
        ("Toro/B3", "B3-negociacao", "B3-movimentacao", "B3-consolidado"),
    ),
    Rail("Tesouro Direto", ("Tesouro Direto Nubank",), ("Aposentadoria",), None),
    Rail(
        "Renda Fixa Nubank",
        ("Caixinha/RDB Nubank", "Renda Fixa Nubank"),
        ("Renda Fixa",),
        ("Nubank", "Guanabara"),
    ),
    Rail("Debêntures Flash", ("Flash Capital debêntures",), ("Renda Fixa",), ("Flash",)),
)

_APLICADO_SQL = (
    "SELECT COALESCE(SUM(CASE "
    "WHEN tipo IN ('compra','aporte') THEN quantidade * valor_unitario "
    "WHEN tipo IN ('venda','resgate') THEN -(quantidade * valor_unitario) "
    "ELSE 0 END), 0) "
    "FROM asset_operations WHERE user_id = $1 AND asset_category = ANY($2)"
)


async def _saiu(conn: asyncpg.Connection, categories: Sequence[str]) -> float:
    """Quanto saiu do Nubank p/ o trilho (líq.): -Σ(amount) do ledger (outflow negativo)."""
    val = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE kind = 'investment' AND category = ANY($1)",
        list(categories),
    )
    return -float(val)


async def _aplicado(conn: asyncpg.Connection, user_id: str, rail: Rail) -> float:
    """Quanto virou posição (custo líq.): compras - vendas em asset_operations."""
    if rail.asset_brokers is None:
        val = await conn.fetchval(_APLICADO_SQL, user_id, list(rail.asset_categories))
    else:
        val = await conn.fetchval(
            _APLICADO_SQL + " AND broker = ANY($3)",
            user_id,
            list(rail.asset_categories),
            list(rail.asset_brokers),
        )
    return float(val)


async def calculate_transit(
    conn: asyncpg.Connection, user_id: str
) -> dict[str, Any]:
    rails: list[dict[str, Any]] = []
    for rail in RAILS:
        saiu = await _saiu(conn, rail.ledger_categories)
        aplicado = await _aplicado(conn, user_id, rail)
        rails.append(
            {
                "rail": rail.name,
                "saiu_brl": round(saiu, 2),
                "aplicado_brl": round(aplicado, 2),
                "em_transito_brl": round(saiu - aplicado, 2),
            }
        )
    # cripto reconcilia pelo sleeve (não é trânsito — carteiras são escaneadas ao vivo).
    from engines.portfolio.crypto_sleeve import calculate_crypto_sleeve  # lazy: evita ciclo

    sleeve = await calculate_crypto_sleeve(conn, user_id)
    crypto = {
        "net_invested_brl": round(float(sleeve["net_invested_brl"]), 2),
        "current_value_brl": round(float(sleeve["current_value_brl"]), 2),
        "resultado_brl": round(float(sleeve["resultado"]), 2),
    }
    return {"rails": rails, "crypto": crypto}
