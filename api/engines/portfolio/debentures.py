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

from engines.common.cache import invalidate_xirr_cache
from engines.common.dates import today_brt
from engines.common.money import Money
from engines.common.owner import get_owner_id
from engines.ledger import queries as ledger_queries
from engines.market import service as market_service
from engines.portfolio import calc
from engines.portfolio.rf import pre_value, rf_rate_assets

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
        base, d = f"{body.issuer}-Debênture", body.start_date
        # o primeiro símbolo livre: emissor, + mês, + dia, + sequência (mesmo emissor e data)
        candidates = [base, f"{base}-{d:%Y%m}", f"{base}-{d:%Y%m%d}"]
        candidates += [f"{base}-{d:%Y%m%d}-{n}" for n in range(2, 100)]
        taken = {
            r["symbol"]
            for r in await conn.fetch(
                "SELECT symbol FROM asset_aliases WHERE symbol = ANY($1::text[])", candidates
            )
        }
        symbol = next(c for c in candidates if c not in taken)
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
    current = await get_debenture(conn, debenture_id)
    # Vencimento enviado como null limpa a data; ausente mantém (os demais campos não aceitam null).
    maturity = (
        body.maturity_date if "maturity_date" in body.model_fields_set else current.maturity_date
    )
    await conn.execute(
        "UPDATE debentures SET issuer = coalesce($2, issuer), rate_label = coalesce($3, "
        "rate_label), monthly_factor = coalesce($4, monthly_factor), start_date = coalesce($5, "
        "start_date), maturity_date = $6 WHERE id = $1::uuid",
        debenture_id,
        body.issuer,
        body.rate_label,
        body.monthly_factor,
        body.start_date,
        maturity,
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
    rail = [t for t, k in keys.items() if (k or "").startswith(RAIL_PREFIX)]
    if not rail:
        return {}
    registered = await conn.fetch(
        "SELECT d.id, d.issuer, d.rate_label, d.start_date FROM debentures d "
        "ORDER BY d.start_date DESC"
    )
    if not registered:
        return {}

    def debenture_for(key: str, day: date) -> asyncpg.Record | None:
        """O trilho nomeia o emissor (`invest:debentures_flash` → Flash): a dele mais recente já
        iniciada na data (ou a primeira dele). Emissor sem debênture cadastrada → sem sugestão."""
        suffix = key.removeprefix(RAIL_PREFIX).strip("_").lower()
        own = [d for d in registered if d["issuer"].lower() == suffix]
        started = [d for d in own if d["start_date"] <= day]
        return started[0] if started else (own[-1] if own else None)

    rows = await conn.fetch(
        "SELECT t.id, t.date, -t.amount AS amount FROM transactions t "
        "WHERE t.id = ANY($1::uuid[]) "
        "AND t.amount < 0 AND NOT EXISTS (SELECT 1 FROM asset_operations o "
        "WHERE o.transaction_id = t.id)",
        rail,
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        debenture = debenture_for(keys[str(r["id"])], r["date"])
        if debenture is None:
            continue
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
    """Revisão confirmada (depois do `categorize`): vale a categoria confirmada. A saída que entrou
    no trilho ganha a sugestão agora; a que saiu dele perde a sugestão pendente; as do trilho com
    aporte sugerido viram a operação ligada (`derived`) e `confirmed`."""
    keys = await ledger_queries.transaction_category_keys(conn, transaction_ids)
    off_rail = [t for t in transaction_ids if not (keys.get(t) or "").startswith(RAIL_PREFIX)]
    await conn.execute(
        "DELETE FROM debenture_contributions WHERE status = 'suggested' "
        "AND transaction_id = ANY($1::uuid[])",
        off_rail,
    )
    on_rail = [t for t in transaction_ids if t not in off_rail]
    if not on_rail:
        return
    await review_suggestions(conn, on_rail)
    rows = await conn.fetch(
        "SELECT c.id, c.transaction_id, c.amount, t.date, a.price_ref, a.id AS asset_id, "
        "d.issuer "
        "FROM debenture_contributions c JOIN transactions t ON t.id = c.transaction_id "
        "JOIN debentures d ON d.id = c.debenture_id JOIN assets a ON a.id = d.asset_id "
        "WHERE c.status = 'suggested' AND c.transaction_id = ANY($1::uuid[]) "
        "AND NOT EXISTS (SELECT 1 FROM asset_operations o WHERE o.transaction_id = t.id)",
        on_rail,
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


async def on_category_changed(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    """Transação que saiu do trilho de debênture (recategorizada depois de confirmada) leva junto o
    aporte derivado dela e a contribuição (se voltar ao trilho, a Revisão sugere de novo). A
    operação protegida (curadoria da 0040) fica."""
    if not transaction_ids:
        return
    keys = await ledger_queries.transaction_category_keys(conn, transaction_ids)
    off_rail = [t for t in transaction_ids if not (keys.get(t) or "").startswith(RAIL_PREFIX)]
    if not off_rail:
        return
    await conn.execute(
        "DELETE FROM asset_operations WHERE transaction_id = ANY($1::uuid[]) "
        "AND external_id LIKE 'debenture:%' AND NOT protected",
        off_rail,
    )
    # a FK zera `operation_id` da contribuição cuja operação saiu; a da protegida fica
    await conn.execute(
        "DELETE FROM debenture_contributions WHERE transaction_id = ANY($1::uuid[]) "
        "AND status IN ('suggested', 'confirmed') AND operation_id IS NULL",
        off_rail,
    )


async def dismiss_contribution(conn: asyncpg.Connection, contribution_id: str) -> None:
    status = await conn.execute(
        "UPDATE debenture_contributions SET status = 'dismissed', updated_at = now() "
        "WHERE id = $1::uuid AND status = 'suggested'",
        contribution_id,
    )
    if status.endswith(" 0"):
        raise DebentureNotFound(contribution_id)


# ---- Integralizações editáveis (P17): as operações de aporte do ativo da debênture ----


class ContributionIn(BaseModel):
    data: date
    valor: Decimal = Field(gt=0)


class ContributionPatch(BaseModel):
    data: date | None = None
    valor: Decimal | None = Field(default=None, gt=0)


class ContributionRow(BaseModel):
    id: str  # a operação de aporte
    data: date
    valor: Money
    saldo: Money  # o valor hoje pela taxa cadastrada (até o vencimento)
    transacao: str | None  # a saída da conta ligada ("dd/mm/aaaa · descrição"), se houver


class ContributionNotFound(LookupError):
    pass


class LinkedContributionError(ValueError):
    """Integralização ligada a uma transação: sai recategorizando a transação, não por aqui."""


class FutureContributionError(ValueError):
    pass


_CONTRIBUTIONS = """
    SELECT o.id::text AS id, o.data_operacao AS data, o.quantidade * o.valor_unitario AS valor,
           t.date AS t_date, t.description AS t_description
    FROM asset_operations o LEFT JOIN transactions t ON t.id = o.transaction_id
    WHERE o.asset_id = $1::uuid AND o.tipo = 'aporte'
"""


async def _target(conn: asyncpg.Connection, debenture_id: str) -> tuple[DebentureRow, Any]:
    debenture = await get_debenture(conn, debenture_id)
    rate = (await rf_rate_assets(conn)).get(debenture.symbol)
    return debenture, rate


async def _reprice(conn: asyncpg.Connection, debenture: DebentureRow, rate: Any) -> None:
    """O preço do ativo (valor pela taxa ÷ quantidade), como o job `rf_cdi` faz todo dia."""
    ops = await conn.fetch(
        "SELECT tipo, quantidade, valor_unitario, data_operacao FROM asset_operations "
        "WHERE asset_id = $1::uuid ORDER BY data_operacao",
        debenture.asset_id,
    )
    qty = calc.quantity(ops)
    if rate is not None and qty > 0:
        value = pre_value(ops, today_brt(), *rate)
        await market_service.upsert_price(
            conn, debenture.symbol, float(value / qty), source="taxa", is_manual=False
        )
    await invalidate_xirr_cache(await get_owner_id(conn))


async def list_contributions(conn: asyncpg.Connection, debenture_id: str) -> list[ContributionRow]:
    debenture, rate = await _target(conn, debenture_id)
    rows = await conn.fetch(_CONTRIBUTIONS + " ORDER BY o.data_operacao DESC", debenture.asset_id)
    today = today_brt()
    out = []
    for r in rows:
        single = [
            {
                "tipo": "aporte",
                "quantidade": r["valor"],
                "valor_unitario": 1,
                "data_operacao": r["data"],
            }
        ]
        saldo = pre_value(single, today, *rate) if rate is not None else Decimal(r["valor"])
        link = (
            f"{r['t_date']:%d/%m/%Y} · {r['t_description'] or 'sem descrição'}"
            if r["t_date"]
            else None
        )
        out.append(
            ContributionRow(
                id=r["id"], data=r["data"], valor=r["valor"], saldo=saldo, transacao=link
            )
        )
    return out


async def add_contribution(
    conn: asyncpg.Connection, debenture_id: str, body: ContributionIn
) -> ContributionRow:
    if body.data > today_brt():
        raise FutureContributionError(body.data)
    debenture, rate = await _target(conn, debenture_id)
    async with conn.transaction():
        op = await conn.fetchval(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao, source, protected, asset_id) "
            "VALUES ($1, $2, $3, 'Renda Fixa', 'aporte', $4, 1, $5, 'manual', true, $6::uuid) "
            "RETURNING id::text",
            await get_owner_id(conn),
            debenture.issuer,
            debenture.symbol,
            body.valor,
            body.data,
            debenture.asset_id,
        )
        await _reprice(conn, debenture, rate)
    return next(c for c in await list_contributions(conn, debenture_id) if c.id == op)


async def update_contribution(
    conn: asyncpg.Connection, debenture_id: str, operation_id: str, body: ContributionPatch
) -> ContributionRow:
    if body.data is not None and body.data > today_brt():
        raise FutureContributionError(body.data)
    debenture, rate = await _target(conn, debenture_id)
    async with conn.transaction():
        status = await conn.execute(
            "UPDATE asset_operations SET data_operacao = coalesce($3, data_operacao), "
            "quantidade = coalesce($4, quantidade), valor_unitario = CASE WHEN $4::numeric IS NULL "
            "THEN valor_unitario ELSE 1 END WHERE id = $1::uuid AND asset_id = $2::uuid "
            "AND tipo = 'aporte'",
            operation_id,
            debenture.asset_id,
            body.data,
            body.valor,
        )
        if status.endswith(" 0"):
            raise ContributionNotFound(operation_id)
        if body.valor is not None:
            await conn.execute(
                "UPDATE debenture_contributions SET amount = $2, updated_at = now() "
                "WHERE operation_id = $1::uuid",
                operation_id,
                body.valor,
            )
        await _reprice(conn, debenture, rate)
    return next(c for c in await list_contributions(conn, debenture_id) if c.id == operation_id)


async def delete_contribution(
    conn: asyncpg.Connection, debenture_id: str, operation_id: str
) -> None:
    debenture, rate = await _target(conn, debenture_id)
    row = await conn.fetchrow(
        "SELECT transaction_id FROM asset_operations WHERE id = $1::uuid AND asset_id = $2::uuid "
        "AND tipo = 'aporte'",
        operation_id,
        debenture.asset_id,
    )
    if row is None:
        raise ContributionNotFound(operation_id)
    if row["transaction_id"] is not None:
        raise LinkedContributionError(operation_id)
    async with conn.transaction():
        await conn.execute("DELETE FROM asset_operations WHERE id = $1::uuid", operation_id)
        await _reprice(conn, debenture, rate)
