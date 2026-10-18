"""Debêntures cadastradas no app (Story 7.6 — FR-24): o cadastro (emissor, taxa, início,
vencimento) sobre um ativo `valuation = 'taxa'` e o aporte sugerido na Revisão de transações.

Sugestão: só saída (aporte) no trilho de investimento em debênture (`invest:debentures_*`) e só se a
transação ainda não tem operação ligada; entrada nunca vira aporte (a receita da Flash é do mesmo
pagador). Confirmar a transação na Revisão cria a operação `aporte` ligada (`derived`); dispensar
grava `dismissed` e nada muda no portfolio. AD-9: só a decisão é gravada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from engines.common.money import Money
from engines.common.owner import get_owner_id
from engines.ledger import queries as ledger_queries

RAIL_PREFIX = "invest:debentures"


class DebentureIn(BaseModel):
    issuer: str = Field(min_length=1)
    rate_label: str = Field(min_length=1)  # "Pré 24% a.a."
    monthly_factor: Decimal = Field(gt=0)  # % a.m. (1,78)
    start_date: date
    maturity_date: date | None = None


class DebenturePatch(BaseModel):
    issuer: str | None = Field(default=None, min_length=1)
    rate_label: str | None = Field(default=None, min_length=1)
    monthly_factor: Decimal | None = Field(default=None, gt=0)
    start_date: date | None = None
    maturity_date: date | None = None


class DebentureRow(BaseModel):
    id: str
    asset_id: str
    symbol: str
    issuer: str
    rate_label: str
    monthly_factor: Decimal
    start_date: date
    maturity_date: date | None
    aplicado: Money  # Σ aportes − resgates ligados ao ativo


class DebentureNotFound(LookupError):
    pass


_ROW = """
    SELECT d.id::text AS id, d.asset_id::text AS asset_id, a.price_ref AS symbol, d.issuer,
           d.rate_label, d.monthly_factor, d.start_date, d.maturity_date,
           coalesce((SELECT sum(CASE WHEN o.tipo IN ('compra', 'aporte') THEN 1
                                     WHEN o.tipo IN ('venda', 'resgate') THEN -1 ELSE 0 END
                                * o.quantidade * o.valor_unitario)
                     FROM asset_operations o WHERE o.asset_id = d.asset_id), 0) AS aplicado
    FROM debentures d JOIN assets a ON a.id = d.asset_id
"""


def _row(r: asyncpg.Record) -> DebentureRow:
    return DebentureRow(**dict(r))


async def list_debentures(conn: asyncpg.Connection) -> list[DebentureRow]:
    return [_row(r) for r in await conn.fetch(_ROW + " ORDER BY d.start_date, d.issuer")]


async def get_debenture(conn: asyncpg.Connection, debenture_id: str) -> DebentureRow:
    row = await conn.fetchrow(_ROW + " WHERE d.id = $1::uuid", debenture_id)
    if row is None:
        raise DebentureNotFound(debenture_id)
    return _row(row)


async def create_debenture(conn: asyncpg.Connection, body: DebentureIn) -> DebentureRow:
    """Cria o ativo (renda fixa, valorado pela taxa) e o cadastro da debênture."""
    async with conn.transaction():
        symbol = f"{body.issuer}-Debênture"
        taken = await conn.fetchval(
            "SELECT count(*) FROM asset_aliases WHERE symbol LIKE $1 || '%'", symbol
        )
        if taken:
            symbol = f"{symbol}-{body.start_date:%Y%m}"
        asset = await conn.fetchval(
            "SELECT goodies_resolve_asset(goodies_op_chain('renda_fixa'), $1, 'renda_fixa')",
            symbol,
        )
        await conn.execute(
            "UPDATE assets SET valuation = 'taxa', name = $2 WHERE id = $1", asset, symbol
        )
        debenture = await conn.fetchval(
            "INSERT INTO debentures (asset_id, issuer, rate_label, monthly_factor, start_date, "
            "maturity_date) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id::text",
            asset,
            body.issuer,
            body.rate_label,
            body.monthly_factor,
            body.start_date,
            body.maturity_date,
        )
    return await get_debenture(conn, debenture)


async def update_debenture(
    conn: asyncpg.Connection, debenture_id: str, body: DebenturePatch
) -> DebentureRow:
    await get_debenture(conn, debenture_id)
    await conn.execute(
        "UPDATE debentures SET issuer = coalesce($2, issuer), rate_label = coalesce($3, "
        "rate_label), monthly_factor = coalesce($4, monthly_factor), start_date = coalesce($5, "
        "start_date), maturity_date = coalesce($6, maturity_date) WHERE id = $1::uuid",
        debenture_id,
        body.issuer,
        body.rate_label,
        body.monthly_factor,
        body.start_date,
        body.maturity_date,
    )
    return await get_debenture(conn, debenture_id)


# ---- Aporte sugerido na Revisão ----


async def review_suggestions(
    conn: asyncpg.Connection, transaction_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Suggester do `ledger` (Revisão): para cada saída do trilho de debênture sem operação ligada,
    a contribuição `suggested` (criada se ainda não existe; `dismissed` não volta)."""
    if not transaction_ids:
        return {}
    keys = await ledger_queries.transaction_category_keys(conn, transaction_ids)
    rail = [t for t, k in keys.items() if k.startswith(RAIL_PREFIX)]
    if not rail:
        return {}
    registered = await conn.fetch(
        "SELECT d.id, d.issuer, d.rate_label FROM debentures d ORDER BY d.start_date DESC"
    )
    if not registered:
        return {}

    def debenture_for(key: str) -> asyncpg.Record:
        """O trilho nomeia o emissor (`invest:debentures_flash` → Flash); senão, a mais recente."""
        suffix = key.removeprefix(RAIL_PREFIX).strip("_").lower()
        return next((d for d in registered if d["issuer"].lower() == suffix), registered[0])

    rows = await conn.fetch(
        "SELECT t.id, -t.amount AS amount FROM transactions t WHERE t.id = ANY($1::uuid[]) "
        "AND t.amount < 0 AND NOT EXISTS (SELECT 1 FROM asset_operations o "
        "WHERE o.transaction_id = t.id)",
        rail,
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        debenture = debenture_for(keys[str(r["id"])])
        contribution = await conn.fetchrow(
            "INSERT INTO debenture_contributions (transaction_id, debenture_id, amount, status) "
            "VALUES ($1, $2, $3, 'suggested') ON CONFLICT (transaction_id) DO UPDATE "
            "SET updated_at = debenture_contributions.updated_at RETURNING id::text, status",
            r["id"],
            debenture["id"],
            r["amount"],
        )
        if contribution["status"] != "suggested":
            continue
        out[str(r["id"])] = {
            "contribution_id": contribution["id"],
            "label": f"{debenture['issuer']} · {debenture['rate_label']}",
            "amount": r["amount"],
        }
    return out


async def on_review_confirmed(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    """Revisão confirmada: aporte sugerido vira a operação ligada (`derived`) e `confirmed`."""
    rows = await conn.fetch(
        "SELECT c.id, c.transaction_id, c.amount, t.date, a.price_ref, a.id AS asset_id, "
        "d.issuer "
        "FROM debenture_contributions c JOIN transactions t ON t.id = c.transaction_id "
        "JOIN debentures d ON d.id = c.debenture_id JOIN assets a ON a.id = d.asset_id "
        "WHERE c.status = 'suggested' AND c.transaction_id = ANY($1::uuid[]) "
        "AND NOT EXISTS (SELECT 1 FROM asset_operations o WHERE o.transaction_id = t.id)",
        transaction_ids,
    )
    if not rows:
        return
    owner = await get_owner_id(conn)
    for r in rows:
        operation = await conn.fetchval(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao, external_id, source, transaction_id, "
            "asset_id) VALUES ($1, $8, $2, 'Renda Fixa', 'aporte', $3, 1, $4, $5, "
            "'derived', $6, $7) RETURNING id",
            owner,
            r["price_ref"],
            r["amount"],
            r["date"],
            f"debenture:{r['transaction_id']}",
            r["transaction_id"],
            r["asset_id"],
            r["issuer"],
        )
        await conn.execute(
            "UPDATE debenture_contributions SET status = 'confirmed', operation_id = $2, "
            "updated_at = now() WHERE id = $1",
            r["id"],
            operation,
        )


async def dismiss_contribution(conn: asyncpg.Connection, contribution_id: str) -> None:
    status = await conn.execute(
        "UPDATE debenture_contributions SET status = 'dismissed', updated_at = now() "
        "WHERE id = $1::uuid AND status = 'suggested'",
        contribution_id,
    )
    if status.endswith(" 0"):
        raise DebentureNotFound(contribution_id)
