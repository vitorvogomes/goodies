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
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
            "description, review_status, category_source) VALUES ($1::uuid, $2, $3, $4, "
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

    issuer = "Flash"  # o trilho `invest:debentures_flash` nomeia o emissor
    async with pool.acquire() as conn:  # sobras de uma rodada interrompida
        stale = [
            r["asset_id"]
            for r in await conn.fetch(
                "SELECT asset_id FROM debentures WHERE issuer LIKE 'Emissor%' "
                "OR start_date >= '2099-01-01'"
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
        other_key = await conn.fetchval(
            "SELECT c.key FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE g.kind = 'expense' AND c.key IS NOT NULL ORDER BY c.key LIMIT 1"
        )
        other_id = str(await conn.fetchval("SELECT id FROM categories WHERE key = $1", other_key))
        rail_id = str(
            await conn.fetchval("SELECT id FROM categories WHERE key = 'invest:debentures_flash'")
        )
        fora = await _tx(conn, account, "invest:debentures_flash", "-200.00", date(2099, 2, 6))
        dentro = await _tx(conn, account, other_key, "-150.00", date(2099, 2, 7))
    try:
        r = await api.patch(
            f"{URL}/{deb['id']}", json={"rate_label": "Pré 21% a.a."}, headers=auth_headers
        )
        assert r.status_code == 200 and r.json()["rate_label"] == "Pré 21% a.a."
        r = await api.patch(
            f"{URL}/{deb['id']}", json={"maturity_date": None}, headers=auth_headers
        )
        assert r.status_code == 200 and r.json()["maturity_date"] is None  # limpar o vencimento
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
                    *(
                        {"transaction_id": t, "category_id": items[t]["category_id"]}
                        for t in (aporte, outro)
                    ),
                    # trocada na Revisão: sai do trilho / entra no trilho
                    {"transaction_id": fora, "category_id": other_id},
                    {"transaction_id": dentro, "category_id": rail_id},
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
                    [aporte, outro, fora, dentro],
                )
            }
            tx_asset = await conn.fetchval(
                "SELECT asset_id::text FROM transactions WHERE id = $1::uuid", aporte
            )
        assert set(ops) == {aporte, dentro}  # nem o dispensado nem o que saiu do trilho
        assert ops[dentro]["quantidade"] == Decimal("150")
        assert (ops[aporte]["tipo"], ops[aporte]["quantidade"]) == ("aporte", Decimal("500"))
        assert ops[aporte]["asset"] == deb["asset_id"] == tx_asset
        listed = {d["id"]: d for d in (await api.get(URL, headers=auth_headers)).json()}
        assert listed[deb["id"]]["aplicado"] == 650.0  # 500 + 150 da que entrou no trilho
        again = (await api.get("/api/v1/ledger/review?mes=2099-02", headers=auth_headers)).json()
        assert aporte not in {i["id"] for i in again["items"]}
        # recategorizada depois de confirmada: o aporte derivado sai junto
        r = await api.patch(
            f"/api/v1/ledger/transactions/{dentro}/category",
            json={"category_id": other_id},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        async with pool.acquire() as conn:
            left = await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE transaction_id = $1::uuid", dentro
            )
            contribution = await conn.fetchval(
                "SELECT count(*) FROM debenture_contributions WHERE transaction_id = $1::uuid",
                dentro,
            )
        assert (left, contribution) == (0, 0)
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM asset_operations WHERE transaction_id = ANY($1::uuid[])",
                [aporte, outro, entrada, fora, dentro],
            )
            await conn.execute(
                "DELETE FROM transactions WHERE id = ANY($1::uuid[])",
                [aporte, outro, entrada, fora, dentro],
            )
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", deb["asset_id"])


@pytest.mark.asyncio
async def test_same_issuer_same_month_gets_its_own_asset(api, auth_headers, pool) -> None:
    """Revisão do Épico 7: a segunda debênture do mesmo emissor no mesmo mês era 500 (o ativo
    resolvido já tinha debênture)."""
    import main  # noqa: F401

    issuer = f"Emissor{uuid.uuid4().hex[:4]}"
    created: list[dict[str, Any]] = []
    try:
        for day in ("2099-03-05", "2099-03-20", "2099-03-20"):
            r = await api.post(
                URL,
                json={
                    "issuer": issuer,
                    "rate_label": "Pré 20% a.a.",
                    "monthly_factor": "1.53",
                    "start_date": day,
                },
                headers=auth_headers,
            )
            assert r.status_code == 201, r.text
            created.append(r.json())
        assert len({d["asset_id"] for d in created}) == 3
    finally:
        async with pool.acquire() as conn:
            for d in created:
                await conn.execute("DELETE FROM debentures WHERE id = $1::uuid", d["id"])
                await conn.execute(
                    "DELETE FROM asset_aliases WHERE asset_id = $1::uuid", d["asset_id"]
                )
                await conn.execute("DELETE FROM assets WHERE id = $1::uuid", d["asset_id"])
