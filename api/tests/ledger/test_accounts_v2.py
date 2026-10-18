"""Story 10.1 — Ajustes › Contas: conta, tipo (PF/MEI) e fonte, criar e editar; a conta MEI fica
marcada como sem conferência de saldo (a conferência encadeada é só da PF)."""

from __future__ import annotations

import uuid

import pytest

from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers

URL = "/api/v1/accounts"


@pytest.mark.asyncio
async def test_holder_source_and_balance_check(api, auth_headers, pool) -> None:
    created: list[str] = []
    try:
        r = await api.post(
            URL,
            json={"name": f"MEI {uuid.uuid4().hex[:4]}", "type": "bank", "holder": "mei"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        mei = r.json()
        created.append(mei["id"])
        assert (mei["holder"], mei["conferencia"], mei["fonte"]) == ("mei", False, "Nubank MEI")
        r = await api.put(f"{URL}/{mei['id']}", json={"holder": "pf"}, headers=auth_headers)
        assert r.status_code == 200 and r.json()["conferencia"] is True
        assert r.json()["fonte"] == "Nubank PF"
        bad = await api.post(
            URL, json={"name": "x", "type": "bank", "holder": "cnpj"}, headers=auth_headers
        )
        assert bad.status_code == 422
        listed = {a["id"]: a for a in (await api.get(URL, headers=auth_headers)).json()}
        assert listed[mei["id"]]["holder"] == "pf"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounts WHERE id = ANY($1::uuid[])", created)


@pytest.mark.asyncio
async def test_second_pf_account_is_refused(api, auth_headers, pool) -> None:
    """A conferência de saldo lê a (única) conta PF: uma segunda PF desviaria a conferência."""
    created: list[str] = []
    try:
        first = await api.post(
            URL,
            json={"name": f"PF {uuid.uuid4().hex[:4]}", "type": "bank", "holder": "pf"},
            headers=auth_headers,
        )
        assert first.status_code == 201, first.text
        created.append(first.json()["id"])
        other = await api.post(
            URL,
            json={"name": f"Corretora {uuid.uuid4().hex[:4]}", "type": "broker"},
            headers=auth_headers,
        )
        created.append(other.json()["id"])
        assert other.json()["holder"] is None
        again = await api.post(
            URL,
            json={"name": f"PF2 {uuid.uuid4().hex[:4]}", "type": "bank", "holder": "pf"},
            headers=auth_headers,
        )
        assert again.status_code == 409
        assert again.json()["detail"]["message"] == "Já existe uma conta PF."
        moved = await api.put(
            f"{URL}/{other.json()['id']}", json={"holder": "pf"}, headers=auth_headers
        )
        assert moved.status_code == 409
        same = await api.put(
            f"{URL}/{first.json()['id']}",
            json={"name": "PF renomeada", "holder": "pf"},
            headers=auth_headers,
        )
        assert same.status_code == 200  # a própria PF continua editável
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounts WHERE id = ANY($1::uuid[])", created)
