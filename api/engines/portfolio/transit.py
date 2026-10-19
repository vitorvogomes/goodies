"""Reconciliação de trânsito (Pilar 2): "quanto saiu do Nubank vs quanto virou posição".

Por trilho de investimento: o ledger registra o que SAIU do Nubank (kind=investment, por
categoria); o `asset_operations` registra o que VIROU POSIÇÃO (custo líquido de compras -
vendas) e os PROVENTOS (dividendo/juros). Mapa validado em 2026-06-07 (ver memória
`ledger-reconciliation-map`).

O número-título por trilho é o RESÍDUO = `saiu + proventos - aplicado` = caixa real na
corretora. Ele é universalmente correto independente de o provento ter ficado na corretora
ou voltado ao Nubank: se voltou, já está netado em `saiu` (o +proventos cancela → não conta
como caixa); se ficou, `saiu` não o viu (o +proventos conta como caixa). O `em_transito`
puro (saiu-aplicado) é só detalhe — vira meio-número quando há proventos.

Cripto NÃO é trânsito (as carteiras são escaneadas ao vivo): reconcilia pelo sleeve
(investido vs valor atual), exposto à parte para não confundir perda com trânsito.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg

from engines.ledger import queries as ledger_queries


@dataclass(frozen=True)
class Rail:
    name: str
    ledger_keys: tuple[str, ...]  # `categories.key` do ledger (kind=investment) — Story 2.3
    asset_categories: tuple[str, ...]  # categorias em asset_operations
    asset_brokers: tuple[str, ...] | None  # None = qualquer broker
    # só a corretora guarda dinheiro esperando virar ativo; nos outros
    # trilhos a aplicação vira ativo na hora e o resíduo é diferença de conciliação
    holds_cash: bool = False


# Trilhos não-cripto. asset_brokers desambigua RF Nubank x Flash (mesma categoria).
RAILS: tuple[Rail, ...] = (
    Rail(
        "B3 (corretoras)",
        ("invest:toro_b3",),
        ("Ações Nacionais", "ETFs", "FIIs"),
        ("Toro/B3", "B3-negociacao", "B3-movimentacao", "B3-consolidado"),
        holds_cash=True,
    ),
    Rail("Tesouro Direto", ("invest:tesouro_nubank",), ("Aposentadoria",), None),
    Rail(
        "Renda Fixa Nubank",
        ("invest:caixinha_rdb", "invest:renda_fixa_nubank"),
        ("Renda Fixa",),
        ("Nubank", "Guanabara"),
    ),
    Rail("Debêntures Flash", ("invest:debentures_flash",), ("Renda Fixa",), ("Flash",)),
)

# Tolerância de reconciliação (R$): centralizada aqui (o front não decide mais a regra).
_RECONCILE_TOL = 1.0

# aplicado (compra-venda) e proventos (dividendo+juros) numa só varredura por trilho.
_APLICADO_SQL = (
    "SELECT "
    "COALESCE(SUM(CASE "
    "WHEN tipo IN ('compra','aporte') THEN quantidade * valor_unitario "
    "WHEN tipo IN ('venda','resgate') THEN -(quantidade * valor_unitario) "
    "ELSE 0 END), 0) AS aplicado, "
    "COALESCE(SUM(CASE "
    "WHEN tipo IN ('dividendo','juros') THEN quantidade * valor_unitario "
    "ELSE 0 END), 0) AS proventos "
    "FROM asset_operations WHERE user_id = $1 AND asset_category = ANY($2)"
)


async def _saiu(conn: asyncpg.Connection, keys: Sequence[str]) -> float:
    """Quanto saiu do Nubank p/ o trilho (líq.): -Σ(amount) do ledger (outflow negativo), lido por
    `categories.key` pela função pública do ledger (AD-3)."""
    # Story 2.6: o resgate do trilho virou receita (`resgate:x`); o líquido lê as duas keys do par.
    rows = await ledger_queries.transactions_by_category_keys(conn, keys, with_pairs=True)
    return -float(sum((r["amount"] for r in rows), Decimal(0)))


async def _aplicado(
    conn: asyncpg.Connection, user_id: str, rail: Rail
) -> tuple[float, float]:
    """(aplicado, proventos): custo líq. (compras-vendas) e dividendos+juros do trilho."""
    if rail.asset_brokers is None:
        row = await conn.fetchrow(_APLICADO_SQL, user_id, list(rail.asset_categories))
    else:
        row = await conn.fetchrow(
            _APLICADO_SQL + " AND broker = ANY($3)",
            user_id,
            list(rail.asset_categories),
            list(rail.asset_brokers),
        )
    return float(row["aplicado"]), float(row["proventos"])


def _residual_status(caixa: float) -> str:
    """Estado do trilho pelo RESÍDUO (saiu + proventos - aplicado = caixa na corretora),
    decidido no backend, não no front:
    - reconciled: |caixa| dentro da tolerância (tudo virou posição ou já voltou ao Nubank);
    - caixa_em_corretora: caixa > 0 parado na corretora (proventos/venda/transferência
      recente ainda não reinvestidos — inclui o trânsito legítimo de relatório atrasado);
    - rendimento_reinvestido: caixa < 0, posição cresceu além do que saiu sem provento
      registrado (anomalia rara — rendimento embutido no custo)."""
    if caixa > _RECONCILE_TOL:
        return "caixa_em_corretora"
    if caixa < -_RECONCILE_TOL:
        return "rendimento_reinvestido"
    return "reconciled"


async def calculate_transit(
    conn: asyncpg.Connection, user_id: str
) -> dict[str, Any]:
    rails: list[dict[str, Any]] = []
    for rail in RAILS:
        saiu = await _saiu(conn, rail.ledger_keys)
        aplicado, proventos = await _aplicado(conn, user_id, rail)
        em_transito = saiu - aplicado
        # Resíduo real = caixa na corretora = saiu + proventos - aplicado. É o número-título
        # do trilho (sempre presente). em_transito (saiu-aplicado) e os proventos ficam como
        # detalhe — o em_transito sozinho é meio-número quando há proventos.
        caixa = round(em_transito + proventos, 2)
        rails.append(
            {
                "rail": rail.name,
                "saiu_brl": round(saiu, 2),
                "aplicado_brl": round(aplicado, 2),
                "em_transito_brl": round(em_transito, 2),
                "dividendos_juros_brl": round(proventos, 2),
                "caixa_corretora_brl": caixa,
                "status": _residual_status(caixa),
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
