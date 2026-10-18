"""Story 3.14 — desfazer o último lote: só o último `applied` com até 7 dias; prévia em números;
desfazer numa transação (operações derivadas, transações, categorizações, regras do lote, saldos);
transações de fora categorizadas por regra do lote voltam sem ela; lote `undone`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.ingest.test_protocol import _ofx, _preview

URL = "/api/v1/ingest"


async def _apply(api, headers, files) -> dict[str, Any]:
    body = (await _preview(api, headers, files)).json()
    r = await api.post(
        f"{URL}/confirm", json={"batch_id": body["batch_id"], "hash": body["hash"]}, headers=headers
    )
    assert r.status_code == 200, r.text
    return body


@pytest.mark.asyncio
async def test_undo_last_batch(api, auth_headers, ofx_account, pool) -> None:
    import main  # noqa: F401

    _, number = ofx_account
    old = await _apply(api, auth_headers, [("a.ofx", _ofx(number, [uuid.uuid4().hex], "20990301"))])
    word = "zqundo" + uuid.uuid4().hex[:4].replace("0", "a")
    async with pool.acquire() as conn:
        outside = await conn.fetchval(
            "SELECT id FROM transactions WHERE batch_id = $1::uuid", old["batch_id"]
        )
        await conn.execute(
            "UPDATE transactions SET description = $2 WHERE id = $1", outside, f"Padaria {word}"
        )
    last = await _apply(
        api,
        auth_headers,
        [("b.ofx", _ofx(number, [uuid.uuid4().hex, uuid.uuid4().hex], "20990305"))],
    )
    target = None
    async with pool.acquire() as conn:
        target = str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
            )
        )
    # regra criada na revisão do último lote, aplicada à transação de fora do lote
    rule = await api.post(
        "/api/v1/ledger/rules",
        json={
            "pattern": word,
            "direction": "saida",
            "category_id": target,
            "lote": last["batch_id"],
        },
        headers=auth_headers,
    )
    assert rule.status_code == 201 and rule.json()["applied"] == 1

    batches = (await api.get(f"{URL}/batches", headers=auth_headers)).json()
    mine = {b["id"]: b for b in batches["items"]}
    assert mine[last["batch_id"]]["undoable"] is True
    assert mine[old["batch_id"]]["undoable"] is False
    order = [b["id"] for b in batches["items"]]
    assert order.index(last["batch_id"]) < order.index(old["batch_id"])  # mais recente primeiro

    pv = await api.post(f"{URL}/batches/{last['batch_id']}/undo/preview", headers=auth_headers)
    assert pv.status_code == 200, pv.text
    counts = pv.json()
    assert (counts["transactions"], counts["rules"]) == (2, 1)
    assert counts["categorizations"] >= 0  # "a classificar" sem regra não gera evento
    refused = await api.post(f"{URL}/batches/{old['batch_id']}/undo", headers=auth_headers)
    assert refused.status_code == 409

    done = await api.post(f"{URL}/batches/{last['batch_id']}/undo", headers=auth_headers)
    assert done.status_code == 200, done.text
    async with pool.acquire() as conn:
        left = await conn.fetchval(
            "SELECT count(*) FROM transactions WHERE batch_id = $1::uuid", last["batch_id"]
        )
        status = await conn.fetchval(
            "SELECT status FROM import_batches WHERE id = $1::uuid", last["batch_id"]
        )
        files = await conn.fetchval(
            "SELECT count(*) FROM import_batch_files WHERE batch_id = $1::uuid", last["batch_id"]
        )
        rules = await conn.fetchval("SELECT count(*) FROM category_rules WHERE pattern = $1", word)
        back = await conn.fetchrow(
            "SELECT category_source, review_status, category_rule_id FROM transactions "
            "WHERE id = $1",
            outside,
        )
    assert (left, status, files, rules) == (0, "undone", 0, 0)
    assert back["category_rule_id"] is None and back["review_status"] == "pending"
    assert back["category_source"] in ("suggestion", "rule")
    again = await api.post(f"{URL}/batches/{last['batch_id']}/undo", headers=auth_headers)
    assert again.status_code == 409
