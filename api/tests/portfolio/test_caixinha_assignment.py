"""Caixinha de cada transação (conciliação de 18/10/2026, P21): desde 19/06/2026 o OFX traz só
"Aplicação RDB" / "Resgate RDB" — a caixinha escolhida na transação vence o casamento pela
descrição; "Saldo separado" é caixa da conta (transferência interna, sem operação)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.portfolio import caixinhas
from tests.ledger.conftest import account as account


async def _tx(conn: Any, account: str, amount: str, description: str) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, description) "
            "VALUES ($1::uuid, $2, $3, (SELECT id FROM categories WHERE key = $4), "
            "'investment', $5) RETURNING id",
            account,
            date(2096, 10, 2),
            Decimal(amount),
            "invest:caixinha_rdb" if Decimal(amount) < 0 else "resgate:caixinha_rdb",
            description,
        )
    )


async def _op(conn: Any, tx: str) -> Any:
    return await conn.fetchrow(
        "SELECT asset_symbol, tipo, quantidade FROM asset_operations "
        "WHERE transaction_id = $1::uuid",
        tx,
    )


@pytest.mark.asyncio
async def test_assign_caixinha_wins_over_description(pool: Any, account: str) -> None:
    import main  # noqa: F401 — hooks do ledger → portfolio

    async with pool.acquire() as conn:
        await conn.execute(  # a base de teste pode não ter a Turbo (a real tem, revisão 0038)
            "INSERT INTO assets (key, name, class, price_ref, valuation, pct_cdi) VALUES "
            "('caixinha:turbo', 'Nubank-Turbo', 'renda_fixa', 'Nubank-Turbo', 'cdi', 115) "
            "ON CONFLICT (key) DO NOTHING"
        )
        tx = await _tx(conn, account, "-4000", "Aplicação RDB")
        try:
            options = {o.key: o for o in await caixinhas.caixinha_options(conn)}
            assert "caixinha:anamaria" in options and "separado" in options
            assert "caixinha:encerradas" not in options

            await caixinhas.assign_caixinha(conn, tx, "caixinha:anamaria")
            op = await _op(conn, tx)
            assert (op["asset_symbol"], op["tipo"], op["quantidade"]) == (
                "Nubank-AnaMaria",
                "aporte",
                Decimal("4000"),
            )
            assert (
                await conn.fetchval(
                    "SELECT a.key FROM transactions t JOIN assets a ON a.id = t.asset_id "
                    "WHERE t.id = $1::uuid",
                    tx,
                )
                == "caixinha:anamaria"
            )

            await caixinhas.assign_caixinha(conn, tx, "caixinha:turbo")  # trocar a caixinha
            assert (await _op(conn, tx))["asset_symbol"] == "Nubank-Turbo"

            await caixinhas.assign_caixinha(conn, tx, "separado")  # caixa da conta
            assert await _op(conn, tx) is None
            row = await conn.fetchrow(
                "SELECT c.key, t.kind FROM transactions t "
                "JOIN categories c ON c.id = t.category_id WHERE t.id = $1::uuid",
                tx,
            )
            assert (row["key"], row["kind"]) == ("transfer:saldo_separado", "transfer")
            assert not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM transaction_caixinha "
                "WHERE transaction_id = $1::uuid)",
                tx,
            )
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE transaction_id = $1::uuid", tx)


@pytest.mark.asyncio
async def test_assign_refuses_outside_caixinha_rail(pool: Any, account: str) -> None:
    async with pool.acquire() as conn:
        tx = str(
            await conn.fetchval(
                "INSERT INTO transactions (account_id, date, amount, kind, description) "
                "VALUES ($1::uuid, '2096-10-03', -50, 'expense', 'Mercado') RETURNING id",
                account,
            )
        )
        with pytest.raises(caixinhas.NotCaixinhaError):
            await caixinhas.assign_caixinha(conn, tx, "caixinha:turbo")
        with pytest.raises(LookupError):
            await caixinhas.assign_caixinha(conn, tx, "caixinha:nao_existe")


@pytest.mark.asyncio
async def test_caixinha_routes(api: Any, auth_headers: dict, pool: Any, account: str) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        tx = await _tx(conn, account, "-700", "Aplicação RDB")
    try:
        listed = (await api.get("/api/v1/portfolio/caixinhas", headers=auth_headers)).json()
        assert {"key": "separado", "label": "Saldo separado (caixa da conta)"} in [
            {"key": o["key"], "label": o["label"]} for o in listed
        ]
        r = await api.put(
            f"/api/v1/portfolio/caixinhas/transactions/{tx}",
            json={"caixinha": "caixinha:anamaria"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        bad = await api.put(
            f"/api/v1/portfolio/caixinhas/transactions/{tx}",
            json={"caixinha": "caixinha:nao_existe"},
            headers=auth_headers,
        )
        assert bad.status_code == 422
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_operations WHERE transaction_id = $1::uuid", tx)
