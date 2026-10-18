"""Story 3.11 — proposta de regra a partir da correção: condição proposta pela descrição, quantas
outras transações afeta, e criar aplica a regra às afetadas que não são manuais."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from engines.ledger.importer import StatementEntry, import_statement
from engines.ledger.service import propose_pattern

URL = "/api/v1/ledger/rules"


def _letters() -> str:
    return "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])


def test_propose_pattern_takes_the_merchant() -> None:
    assert propose_pattern("Compra no débito - BOI NA CHAPA") == "boi na chapa"
    assert (
        propose_pattern("Transferência enviada pelo Pix - JT SUPLEMENTOS - 58.403.760/0001-1 - X")
        == "jt suplementos"
    )
    assert propose_pattern("UBER *TRIP 1234") == "uber *trip"


@pytest.mark.asyncio
async def test_propose_and_create(api, auth_headers, account, pool) -> None:
    word = f"Loja Zq{_letters()}"
    entries = [
        StatementEntry(
            uuid.uuid4().hex,
            datetime.date(2099, 7, d),
            Decimal(f"-{d}"),
            f"Compra no débito - {word}",
        )
        for d in (1, 2, 3)
    ]
    async with pool.acquire() as conn:
        await import_statement(conn, uuid.UUID(account), entries)
        ids = [
            str(r["id"])
            for r in await conn.fetch(
                "SELECT id FROM transactions WHERE account_id = $1::uuid ORDER BY date", account
            )
        ]
        target = str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
            )
        )
        # a 3ª foi corrigida à mão antes: a regra não mexe nela
        await conn.execute(
            "UPDATE transactions SET category_source = 'manual' WHERE id = $1::uuid", ids[2]
        )
    r = await api.post(
        f"{URL}/propose",
        json={"transaction_id": ids[0], "category_id": target},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    prop = r.json()
    assert prop["pattern"] == word.lower() and prop["direction"] == "saida"
    assert prop["affected"] == 1  # a outra não manual
    batch = str(uuid.uuid4())
    created = await api.post(
        URL,
        json={"pattern": prop["pattern"], "direction": "saida", "category_id": target},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["applied"] == 2  # a corrigida e a outra; a manual fica
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, category_id::text, category_source FROM transactions "
            "WHERE account_id = $1::uuid ORDER BY date",
            account,
        )
        rule = await conn.fetchrow(
            "SELECT origin, created_in_batch FROM category_rules WHERE pattern = $1", word.lower()
        )
        await conn.execute("DELETE FROM category_rules WHERE pattern = $1", word.lower())
    assert [(r["category_id"], r["category_source"]) for r in rows[:2]] == [(target, "rule")] * 2
    assert rows[2]["category_source"] == "manual"
    assert rule["origin"] == "manual" and rule["created_in_batch"] is None
    assert batch  # created_in_batch é coberto no teste da revisão


@pytest.mark.asyncio
async def test_rule_from_review_records_batch(api, auth_headers, account, pool) -> None:
    word = f"Posto Zq{_letters()}"
    async with pool.acquire() as conn:
        await import_statement(
            conn,
            uuid.UUID(account),
            [StatementEntry(uuid.uuid4().hex, datetime.date(2099, 8, 1), Decimal("-5"), word)],
        )
        batch = str(
            await conn.fetchval(
                "SELECT batch_id FROM transactions WHERE account_id = $1::uuid", account
            )
        )
        target = str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
            )
        )
    created = await api.post(
        URL,
        json={
            "pattern": word.lower(),
            "direction": "saida",
            "category_id": target,
            "lote": batch,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    async with pool.acquire() as conn:
        rule = await conn.fetchrow(
            "SELECT origin, created_in_batch::text FROM category_rules WHERE pattern = $1",
            word.lower(),
        )
        await conn.execute("DELETE FROM category_rules WHERE pattern = $1", word.lower())
    assert (rule["origin"], rule["created_in_batch"]) == ("review", batch)
