"""Story 3.13 — conferência na tela: o Bloco Fontes mostra "conferido" ou "divergente · R$ x" na
conta PF, o provider emite "Saldo divergente em R$ x na conta PF." (divergência) com Ver transações,
e as candidatas do intervalo vêm ordenadas pela proximidade do valor com a diferença."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def pf_account(pool: Any) -> AsyncIterator[str]:
    async with pool.acquire() as conn:
        holders = await conn.fetch("SELECT id FROM accounts WHERE holder = 'pf'")
        await conn.execute("UPDATE accounts SET holder = NULL WHERE holder = 'pf'")
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number, holder) "
            "VALUES ($1, 'bank', $2, 'pf') RETURNING id",
            f"pf-{uuid.uuid4().hex[:6]}",
            str(uuid.uuid4().int)[:9],
        )
    yield str(acc)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM account_balances WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
        await conn.execute(
            "UPDATE accounts SET holder = 'pf' WHERE id = ANY($1::uuid[])",
            [h["id"] for h in holders],
        )


async def _seed(pool: Any, acc: str, reported: list[tuple[date, str]], tx: list[tuple[date, str]]):
    async with pool.acquire() as conn:
        cat = await conn.fetchval(
            "SELECT id FROM categories WHERE key = 'sistema:saida_a_classificar'"
        )
        for d, v in reported:
            await conn.execute(
                "INSERT INTO account_balances (account_id, as_of, balance) "
                "VALUES ($1::uuid, $2, $3)",
                acc,
                d,
                Decimal(v),
            )
        for d, v in tx:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
                "description) VALUES ($1::uuid, $2, $3, 'x', $4, 'expense', $5)",
                acc,
                d,
                Decimal(v),
                cat,
                f"t {v}",
            )


@pytest.mark.asyncio
async def test_conferido(api, auth_headers, pf_account, pool) -> None:
    await _seed(
        pool,
        pf_account,
        [(date(2099, 1, 31), "100.00"), (date(2099, 2, 28), "80.00")],
        [(date(2099, 2, 10), "-20.00")],
    )
    rows = (await api.get("/api/v1/ingest/sources", headers=auth_headers)).json()
    pf = next(r for r in rows if r["key"] == "nubank_pf")
    assert (pf["balance_status"], pf["balance_as_of"]) == ("conferido", "2099-02-28")


@pytest.mark.asyncio
async def test_divergente_alert_and_candidates(api, auth_headers, pf_account, pool) -> None:
    import main  # noqa: F401
    from engines.alerts import service as alerts_service

    await _seed(
        pool,
        pf_account,
        [(date(2099, 1, 31), "100.00"), (date(2099, 2, 28), "50.00")],
        [
            (date(2099, 2, 3), "-5.00"),
            (date(2099, 2, 10), "-20.00"),
            (date(2099, 2, 20), "-31.00"),
        ],
    )  # esperado 44 → diferença +6
    rows = (await api.get("/api/v1/ingest/sources", headers=auth_headers)).json()
    pf = next(r for r in rows if r["key"] == "nubank_pf")
    assert (pf["balance_status"], pf["balance_difference"]) == ("divergente", 6.0)
    async with pool.acquire() as conn:
        items = (await alerts_service.active_alerts(conn)).items
    alert = next(a for a in items if a.key.startswith("saldo_divergente:pf:"))
    assert alert.severity == "divergencia"
    assert alert.message == "Saldo divergente em R$\u00a06,00 na conta PF."
    assert alert.action.label == "Ver transações"
    assert alert.action.params["conferencia"] == "2099-01-31_2099-02-28"
    r = await api.get(
        "/api/v1/ledger/balance-check/candidates?inicio=2099-01-31&fim=2099-02-28",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["difference"] == 6.0
    assert [c["amount"] for c in body["items"]] == [-5.0, -20.0, -31.0]  # |5−6|, |20−6|, |31−6|
