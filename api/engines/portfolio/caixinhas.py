"""Registro e valoração das caixinhas/CDB do Nubank como ativos de Renda Fixa (pré-m3).

As caixinhas (RDB/CDB indexados ao CDI) saem do extrato Nubank mas não existiam no
portfólio. Aqui elas viram `asset_operations` (categoria 'Renda Fixa'), com as
operações DERIVADAS das próprias `transactions` pelos hooks de import e de recategorização
(Stories 3.5 e 7.5); a valoração é a do CDI publicado (`rf.cdi_value`, Story 7.4).

Registro CONFIG-DRIVEN: adicionar uma caixinha = uma linha em CAIXINHAS. A Reserva de
Emergência (próxima a ser criada) já está listada, basta `enabled=True`.

Desde 19/06/2026 o OFX traz só "Aplicação RDB" / "Resgate RDB", sem o nome: a caixinha escolhida na
transação (`transaction_caixinha`, revisão 0046) vence o casamento pela descrição. "Saldo separado"
(o "Separar saldo" do Nubank, que não rende) é caixa da conta: vira transferência interna.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg

from engines.common.assets import AssetCategory
from engines.ledger import queries as ledger_queries
from engines.ledger import service as ledger_service

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
    # Caixinha Ana Maria: criada em out/2026 (o OFX já não traz o nome — escolhida na transação).
    CaixinhaSpec("Nubank-AnaMaria", "Nubank", 100.0, ("ana maria",)),
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
    by_description = await ledger_queries.transactions_by_category_keys(
        conn,
        spec.source_keys,
        description_any=spec.desc_match,
        with_pairs=True,
        ids=transaction_ids,
    )
    chosen = {
        str(r["id"]): r
        for r in await conn.fetch(
            _CHOSEN, list(transaction_ids) if transaction_ids is not None else None
        )
    }
    rows = [r for r in by_description if str(r["id"]) not in chosen]
    rows += [r for r in chosen.values() if r["symbol"] == spec.symbol]
    ops: list[dict[str, Any]] = []
    for r in sorted(rows, key=lambda r: r["date"]):
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


# A caixinha escolhida na transação (só no trilho de caixinha): vence a descrição.
_CHOSEN = """
    SELECT t.id, t.date, t.amount, t.external_id, a.price_ref AS symbol
    FROM transaction_caixinha o
    JOIN transactions t ON t.id = o.transaction_id
    JOIN assets a ON a.id = o.asset_id
    JOIN categories c ON c.id = t.category_id
    WHERE c.key IN ('invest:caixinha_rdb', 'resgate:caixinha_rdb')
      AND ($1::uuid[] IS NULL OR t.id = ANY($1::uuid[]))
"""

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


# --------------------------------------------------------------------------------------------
# A caixinha de cada transação (conciliação de 18/10/2026, P21)
# --------------------------------------------------------------------------------------------

SEPARADO = "separado"
_RAIL_KEYS = ("invest:caixinha_rdb", "resgate:caixinha_rdb")
_SEPARADO_KEY = "transfer:saldo_separado"


class NotCaixinhaError(ValueError):
    """A transação não é aplicação/resgate de caixinha."""


@dataclass(frozen=True)
class CaixinhaOption:
    key: str  # `assets.key` ou "separado"
    label: str
    asset_id: str | None = None


async def caixinha_options(conn: asyncpg.Connection) -> list[CaixinhaOption]:
    """As caixinhas vivas (sem o bucket das encerradas) + "Saldo separado" (caixa da conta)."""
    rows = await conn.fetch(
        "SELECT id::text, key, name FROM assets WHERE key LIKE 'caixinha:%' "
        "AND key <> 'caixinha:encerradas' AND is_active ORDER BY name"
    )
    out = [CaixinhaOption(r["key"], str(r["name"]).removeprefix("Nubank-"), r["id"]) for r in rows]
    return [*out, CaixinhaOption(SEPARADO, "Saldo separado (caixa da conta)")]


async def assign_caixinha(conn: asyncpg.Connection, transaction_id: str, choice: str) -> None:
    """Grava a caixinha da transação e refaz a operação derivada; "separado" tira a transação do
    trilho de caixinha (transferência interna: caixa da conta, fora de aporte e investimento)."""
    if choice not in {o.key for o in await caixinha_options(conn)}:
        raise LookupError(choice)
    tx = await conn.fetchrow(
        "SELECT t.amount, c.key FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.id = $1::uuid",
        transaction_id,
    )
    if tx is None:
        raise LookupError(transaction_id)
    if tx["key"] not in (*_RAIL_KEYS, _SEPARADO_KEY):
        raise NotCaixinhaError(transaction_id)
    async with conn.transaction():
        if choice == SEPARADO:
            await conn.execute(
                "DELETE FROM transaction_caixinha WHERE transaction_id = $1::uuid", transaction_id
            )
            target = _SEPARADO_KEY
        else:
            await conn.execute(
                "INSERT INTO transaction_caixinha (transaction_id, asset_id) "
                "SELECT $1::uuid, id FROM assets WHERE key = $2 "
                "ON CONFLICT (transaction_id) DO UPDATE SET asset_id = EXCLUDED.asset_id",
                transaction_id,
                choice,
            )
            target = _RAIL_KEYS[0] if tx["amount"] < 0 else _RAIL_KEYS[1]
        if tx["key"] != target:
            category = await ledger_queries.category_id_by_key(conn, target)
            await ledger_service.categorize(
                conn,
                [ledger_service.CategoryChange(transaction_id, category, "manual")],
                cause="inline_edit",
                review_status="confirmed",
            )
        else:
            await ledger_service.run_transaction_hooks(conn, [transaction_id])
