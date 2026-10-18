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
