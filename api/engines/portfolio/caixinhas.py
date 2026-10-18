"""Registro e valoração das caixinhas/CDB do Nubank como ativos de Renda Fixa (pré-m3).

As caixinhas (RDB/CDB indexados ao CDI) saem do extrato Nubank mas não existiam no
portfólio. Aqui elas viram `asset_operations` (categoria 'Renda Fixa'), com as
operações DERIVADAS das próprias `transactions` pelos hooks de import e de recategorização
(Stories 3.5 e 7.5); a valoração é a do CDI publicado (`rf.cdi_value`, Story 7.4).

Registro CONFIG-DRIVEN: adicionar uma caixinha = uma linha em CAIXINHAS. A Reserva de
Emergência (próxima a ser criada) já está listada, basta `enabled=True`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg

from engines.common.assets import AssetCategory
from engines.ledger import queries as ledger_queries

_CATEGORY = AssetCategory.RENDA_FIXA


@dataclass(frozen=True)
class CaixinhaSpec:
    """Como localizar (em transactions) e valorar uma caixinha/CDB."""

    symbol: str
    broker: str
    pct_cdi: float  # 100.0 / 115.0 / 117.5
    desc_match: tuple[str, ...]  # tokens ILIKE (case-insensitive) na descrição
    source_keys: tuple[str, ...] = ("invest:caixinha_rdb",)  # `categories.key` (Story 2.3)
    cap: float | None = None  # informativo (ex.: Turbo R$5.000)
    enabled: bool = True


# As caixinhas ativas: Snow Trip (o grosso), Turbo (float/emergência, cap 5k) e Reserva (Nu Reserva
# Imediata, desde jul/2026). HotCash encerrada — enabled=False.
CAIXINHAS: list[CaixinhaSpec] = [
    CaixinhaSpec("Nubank-SnowTrip", "Nubank", 100.0, ("snow",)),
    CaixinhaSpec("Nubank-Turbo", "Nubank", 115.0, ("turbo",), cap=5000.0),
    # Nu Reserva Imediata: criada em jul/2026 (OFX de jul-out/2026), ativa desde então.
    CaixinhaSpec("Nubank-Reserva", "Nubank", 100.0, ("reserva", "resp. ltda")),
    CaixinhaSpec("Nubank-HotCash", "Nubank", 100.0, ("hotcash",), enabled=False),
]

# CDB Guanabara (117,5% CDI, venc. 2028) — fonte diferente (Renda Fixa Nubank).
CDB_GUANABARA = CaixinhaSpec(
    "Guanabara-CDB",
    "Guanabara",
    117.5,
    ("guanabara",),
    source_keys=("invest:renda_fixa_nubank",),
)


async def build_caixinha_ops(
    conn: asyncpg.Connection, spec: CaixinhaSpec, transaction_ids: Sequence[str] | None = None
) -> list[dict[str, Any]]:
    """Deriva aporte/resgate (datados) das transactions que casam o spec.

    aporte = saída (amount<0); resgate = entrada (amount>0). quantidade = |amount|,
    valor_unitario = 1.0 (R$ como quantidade, igual ao seed Flash). Idempotência por
    `transaction_id` (Story 3.5) e por external_id = caixinha:{symbol}:{tx.external_id}.
    """
    if not spec.desc_match:
        return []
    rows = await ledger_queries.transactions_by_category_keys(
        conn,
        spec.source_keys,
        description_any=spec.desc_match,
        with_pairs=True,
        ids=transaction_ids,
    )
    ops: list[dict[str, Any]] = []
    for r in rows:
        amount = float(r["amount"])
        if amount == 0:
            continue
        tipo = "aporte" if amount < 0 else "resgate"
        ext = r["external_id"] or f"{r['date'].isoformat()}:{abs(amount):.2f}"
        ops.append(
            {
                "asset_symbol": spec.symbol,
                "asset_category": _CATEGORY,
                "tipo": tipo,
                "quantidade": abs(amount),
                "valor_unitario": 1.0,
                "data_operacao": r["date"],
                "external_id": f"caixinha:{spec.symbol}:{ext}",
                "transaction_id": str(r["id"]),
            }
        )
    return ops


_DERIVED = """
    SELECT id, transaction_id::text AS transaction_id, asset_symbol, tipo, quantidade,
           data_operacao, protected
    FROM asset_operations
    WHERE transaction_id IS NOT NULL AND ($1::uuid[] IS NULL OR transaction_id = ANY($1::uuid[]))
"""
_INSERT_DERIVED = """
    INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, quantidade,
      valor_unitario, data_operacao, external_id, source, transaction_id)
    VALUES ($1, $2, $3, $4, $5, $6, 1.0, $7, $8, 'derived', $9::uuid)
    ON CONFLICT DO NOTHING
"""
_UPDATE_DERIVED = """
    UPDATE asset_operations SET asset_symbol = $2, tipo = $3, quantidade = $4, data_operacao = $5
    WHERE id = $1 AND NOT protected
"""


async def derive_caixinha_ops(
    conn: asyncpg.Connection, user_id: str, transaction_ids: Sequence[str] | None = None
) -> dict[str, int]:
    """Deixa as operações de caixinha/CDB iguais às transações (Story 3.5): cria as que faltam,
    corrige as que mudaram e apaga as de transação que deixou de ser caixinha. Idempotente por
    `transaction_id`; operação `protected` (curadoria) nunca muda. Sem `transaction_ids`, olha tudo.
    """
    desired: dict[str, tuple[CaixinhaSpec, dict[str, Any]]] = {}
    for spec in [*(s for s in CAIXINHAS if s.enabled), CDB_GUANABARA]:
        for op in await build_caixinha_ops(conn, spec, transaction_ids):
            desired.setdefault(op["transaction_id"], (spec, op))
    scope = list(transaction_ids) if transaction_ids is not None else None
    existing = {r["transaction_id"]: r for r in await conn.fetch(_DERIVED, scope)}
    report = {"created": 0, "updated": 0, "deleted": 0}
    for tx_id, row in existing.items():
        if row["protected"]:
            continue
        if tx_id not in desired:
            if row["asset_symbol"] in _DERIVED_SYMBOLS:
                await conn.execute("DELETE FROM asset_operations WHERE id = $1", row["id"])
                report["deleted"] += 1
            continue
        _, op = desired[tx_id]
        if (row["asset_symbol"], row["tipo"], float(row["quantidade"]), row["data_operacao"]) != (
            op["asset_symbol"],
            op["tipo"],
            op["quantidade"],
            op["data_operacao"],
        ):
            await conn.execute(
                _UPDATE_DERIVED,
                row["id"],
                op["asset_symbol"],
                op["tipo"],
                op["quantidade"],
                op["data_operacao"],
            )
            report["updated"] += 1
    for tx_id, (spec, op) in desired.items():
        if tx_id in existing:
            continue
        status = await conn.execute(
            _INSERT_DERIVED,
            user_id,
            spec.broker,
            op["asset_symbol"],
            str(op["asset_category"]),
            op["tipo"],
            op["quantidade"],
            op["data_operacao"],
            op["external_id"],
            tx_id,
        )
        report["created"] += status.endswith(" 1")
    return report


# Só operações destas caixinhas/CDB são derivadas (e apagáveis pela derivação).
_DERIVED_SYMBOLS = frozenset({*(s.symbol for s in CAIXINHAS), CDB_GUANABARA.symbol})
