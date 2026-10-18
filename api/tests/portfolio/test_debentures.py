"""Story 7.6 — debêntures cadastradas no app: o cadastro cria o ativo valorado pela taxa; na
Revisão, a saída do trilho de debênture sem operação ligada traz o aporte sugerido; confirmar cria
a operação ligada (e o ativo da transação); dispensar não muda nada; entrada nunca é sugerida."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tests.ledger.conftest import account as account
from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers

URL = "/api/v1/portfolio/debentures"


async def _tx(conn: Any, account_id: str, key: str, amount: str, d: date) -> str:
    cat = await conn.fetchval("SELECT id FROM categories WHERE key = $1", key)
    return str(
        await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description, review_status, category_source) VALUES ($1::uuid, $2, $3, 'x', $4, "
            "(SELECT g.kind FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE c.id = $4), $5, 'pending', 'rule') RETURNING id",
            account_id,
            d,
            Decimal(amount),
            cat,
            f"Debênture {uuid.uuid4().hex[:6]}",
        )
    )


@pytest.mark.asyncio
async def test_debenture_crud_and_review_flow(api, auth_headers, account, pool) -> None:
    import main  # noqa: F401

    issuer = f"Emissor{uuid.uuid4().hex[:4]}"
    async with pool.acquire() as conn:  # sobras de uma rodada interrompida
        stale = [
            r["asset_id"]
            for r in await conn.fetch(
                "SELECT asset_id FROM debentures WHERE issuer LIKE 'Emissor%'"
            )
        ]
        await conn.execute(
            "UPDATE transactions SET asset_id = NULL WHERE asset_id = ANY($1)", stale
        )
        await conn.execute("DELETE FROM asset_operations WHERE asset_id = ANY($1)", stale)
        await conn.execute("DELETE FROM assets WHERE id = ANY($1)", stale)
    r = await api.post(
        URL,
        json={
            "issuer": issuer,
            "rate_label": "Pré 20% a.a.",
            "monthly_factor": "1.53",
            "start_date": "2099-01-01",
            "maturity_date": "2101-01-01",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    deb = r.json()
    async with pool.acquire() as conn:
        asset = await conn.fetchrow(
            "SELECT valuation, class FROM assets WHERE id = $1::uuid", deb["asset_id"]
        )
        assert (asset["valuation"], asset["class"]) == ("taxa", "renda_fixa")
        aporte = await _tx(conn, account, "invest:debentures_flash", "-500.00", date(2099, 2, 3))
        outro = await _tx(conn, account, "invest:debentures_flash", "-300.00", date(2099, 2, 4))
        entrada = await _tx(conn, account, "resgate:debentures_flash", "250.00", date(2099, 2, 5))
    try:
        r = await api.patch(
            f"{URL}/{deb['id']}", json={"rate_label": "Pré 21% a.a."}, headers=auth_headers
        )
        assert r.status_code == 200 and r.json()["rate_label"] == "Pré 21% a.a."
        items = {
            i["id"]: i
            for i in (
                await api.get("/api/v1/ledger/review?mes=2099-02", headers=auth_headers)
            ).json()["items"]
        }
        assert items[aporte]["debenture"]["label"] == f"{issuer} · Pré 21% a.a."
        assert items[aporte]["debenture"]["amount"] == 500.0
        assert items[entrada]["debenture"] is None  # entrada nunca vira aporte
        dismiss = items[outro]["debenture"]["contribution_id"]
        r = await api.post(f"{URL}/contributions/{dismiss}/dismiss", headers=auth_headers)
        assert r.status_code == 204
        r = await api.post(
            "/api/v1/ledger/review/confirm",
            json={
                "items": [
                    {"transaction_id": t, "category_id": items[t]["category_id"]}
                    for t in (aporte, outro)
                ]
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        async with pool.acquire() as conn:
            ops = {
                str(r["transaction_id"]): r
                for r in await conn.fetch(
                    "SELECT transaction_id, tipo, quantidade, asset_id::text AS asset "
                    "FROM asset_operations WHERE transaction_id = ANY($1::uuid[])",
                    [aporte, outro],
                )
            }
            tx_asset = await conn.fetchval(
                "SELECT asset_id::text FROM transactions WHERE id = $1::uuid", aporte
            )
        assert set(ops) == {aporte}  # o dispensado não vira operação
        assert (ops[aporte]["tipo"], ops[aporte]["quantidade"]) == ("aporte", Decimal("500"))
        assert ops[aporte]["asset"] == deb["asset_id"] == tx_asset
        listed = {d["id"]: d for d in (await api.get(URL, headers=auth_headers)).json()}
        assert listed[deb["id"]]["aplicado"] == 500.0
        again = (await api.get("/api/v1/ledger/review?mes=2099-02", headers=auth_headers)).json()
        assert aporte not in {i["id"] for i in again["items"]}
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM asset_operations WHERE transaction_id = ANY($1::uuid[])",
                [aporte, outro, entrada],
            )
            await conn.execute(
                "DELETE FROM transactions WHERE id = ANY($1::uuid[])", [aporte, outro, entrada]
            )
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", deb["asset_id"])
