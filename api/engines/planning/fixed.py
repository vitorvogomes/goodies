"""Aportes fixos do mês (pedido de 18/10/2026): o valor que um objetivo (`goal:<id>`) ou um
ativo (`asset:<id>`) recebe todo mês — a integralização da Flash, a caixinha de um objetivo. A
Distribuição do aporte os trata como travas padrão do mês (a trava gravada no próprio mês vence).
Vigência como as metas: salvar grava a versão a partir do mês atual; excluir fecha a vigência no
mês anterior (o que nasceu neste mês sai de vez)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import asyncpg
from pydantic import BaseModel, Field

from engines.common.dates import today_brt
from engines.common.money import Money

from .goals import asset_label

_OPTION_CLASSES = ("renda_fixa", "aposentadoria", "acoes_br", "etfs", "fiis", "cripto")


class FixedIn(BaseModel):
    key: str = Field(pattern=r"^(goal|asset):[0-9a-f-]{36}$")
    amount: Money = Field(gt=0)


class FixedItem(BaseModel):
    id: str
    key: str
    label: str
    amount: Money
    valid_from: date


class FixedOption(BaseModel):
    key: str
    label: str
    group: str  # "Objetivos" | rótulo da classe


class FixedOut(BaseModel):
    items: list[FixedItem]
    options: list[FixedOption]


async def month_fixed(conn: asyncpg.Connection, month: date) -> dict[str, Decimal]:
    """chave → valor dos aportes fixos vigentes no mês."""
    if not await conn.fetchval("SELECT to_regclass('fixed_contributions') IS NOT NULL"):
        return {}
    rows = await conn.fetch(
        "SELECT key, amount FROM fixed_contributions WHERE valid_from <= $1 "
        "AND (valid_to IS NULL OR valid_to >= $1)",
        month,
    )
    return {r["key"]: Decimal(r["amount"]) for r in rows}


async def _labels(conn: asyncpg.Connection) -> list[FixedOption]:
    from .targets import CLASS_LABELS

    labels = dict(CLASS_LABELS)
    goals = [
        FixedOption(key=f"goal:{r['id']}", label=r["name"], group="Objetivos")
        for r in await conn.fetch("SELECT id::text AS id, name FROM goals ORDER BY name")
    ]
    assets = [
        FixedOption(
            key=f"asset:{r['id']}",
            label=asset_label(r["key"], r["name"]),
            group=labels.get(r["class"], r["class"]),
        )
        for r in await conn.fetch(
            "SELECT id::text AS id, key, name, class FROM assets WHERE is_active "
            "AND class = ANY($1::text[]) AND key NOT LIKE 'caixinha:%' ORDER BY class, name",
            list(_OPTION_CLASSES),
        )
    ]
    return goals + assets


async def list_fixed(conn: asyncpg.Connection) -> FixedOut:
    month = today_brt().replace(day=1)
    options = await _labels(conn)
    names = {o.key: o.label for o in options}
    rows = await conn.fetch(
        "SELECT id::text AS id, key, amount, valid_from FROM fixed_contributions "
        "WHERE valid_to IS NULL OR valid_to >= $1 ORDER BY created_at",
        month,
    )
    return FixedOut(
        items=[
            FixedItem(
                id=r["id"],
                key=r["key"],
                label=names.get(r["key"], r["key"]),
                amount=r["amount"],
                valid_from=r["valid_from"],
            )
            for r in rows
        ],
        options=options,
    )


async def save_fixed(conn: asyncpg.Connection, body: FixedIn) -> FixedOut:
    """Grava o valor a partir deste mês: a versão anterior fecha no mês passado (ou é trocada, se
    nasceu neste mês). Chave de objetivo/ativo inexistente → LookupError."""
    kind, ref = body.key.split(":", 1)
    table = "goals" if kind == "goal" else "assets"
    if not await conn.fetchval(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE id = $1::uuid)", ref):
        raise LookupError(body.key)
    month = today_brt().replace(day=1)
    async with conn.transaction():
        await _close(conn, body.key, month)
        await conn.execute(
            "INSERT INTO fixed_contributions (key, amount, valid_from) VALUES ($1, $2, $3)",
            body.key,
            body.amount,
            month,
        )
    return await list_fixed(conn)


async def delete_fixed(conn: asyncpg.Connection, key: str) -> bool:
    month = today_brt().replace(day=1)
    async with conn.transaction():
        return await _close(conn, key, month)


async def _close(conn: asyncpg.Connection, key: str, month: date) -> bool:
    row = await conn.fetchrow(
        "SELECT id, valid_from FROM fixed_contributions WHERE key = $1 AND valid_to IS NULL", key
    )
    if row is None:
        return False
    if row["valid_from"] >= month:
        await conn.execute("DELETE FROM fixed_contributions WHERE id = $1", row["id"])
    else:
        await conn.execute(
            "UPDATE fixed_contributions SET valid_to = $2 WHERE id = $1",
            row["id"],
            month - timedelta(days=1),
        )
    return True
