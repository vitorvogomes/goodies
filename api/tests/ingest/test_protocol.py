"""Story 3.3 — import com prévia e lote: protocolo SourceAdapter, prévia `staged` com hash,
confirmação numa transação, dedup por FITID, "arquivo já importado", overrides e a página v1."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
import pytest_asyncio

from engines.alerts import service as alerts_service
from engines.common.month_status import AllMonthsOpen, register_month_status
from engines.ingest import service as ingest_service

URL = "/api/v1/ingest"


def _ofx(acctid: str, fitids: list[str], day: str = "20990105") -> bytes:
    rows = "".join(
        "<STMTTRN><TRNTYPE>DEBIT</TRNTYPE>"
        f"<DTPOSTED>{day}000000[-3:BRT]</DTPOSTED><TRNAMT>-{10 + i}.00</TRNAMT>"
        f"<FITID>{f}</FITID><MEMO>Padaria {i}\n</STMTTRN>\n"
        for i, f in enumerate(fitids)
    )
    return (
        "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        f"<BANKACCTFROM><ACCTID>{acctid}</ACCTID></BANKACCTFROM>\n<BANKTRANLIST>\n"
        f"{rows}</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode()


def _csv(fitids: list[str]) -> bytes:
    lines = "".join(
        f"0{i + 1}/02/2099,-{20 + i}.00,{f},Mercado {i}\n" for i, f in enumerate(fitids)
    )
    return ("Data,Valor,Identificador,Descrição\n" + lines).encode()


@pytest_asyncio.fixture
async def ofx_account(pool: Any) -> AsyncIterator[tuple[str, str]]:
    number = str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, 'bank', $2) "
            "RETURNING id",
            f"ofx-{number}",
            number,
        )
    yield str(acc), number
    async with pool.acquire() as conn:
        batches = [
            r["batch_id"]
            for r in await conn.fetch(
                "SELECT DISTINCT batch_id FROM transactions WHERE account_id = $1", acc
            )
        ]
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM import_batches WHERE id = ANY($1::uuid[])", batches)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)


async def _preview(api, headers, files: list[tuple[str, bytes]], overrides: str | None = None):
    data = {"overrides": overrides} if overrides else None
    return await api.post(
        f"{URL}/preview",
        files=[("files", (name, content)) for name, content in files],
        data=data,
        headers=headers,
    )


async def _count(pool, account_id: str) -> int:
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE account_id = $1::uuid", account_id
            )
        )


class RecordingPort(AllMonthsOpen):
    def __init__(self) -> None:
        self.dirty: list[date] = []

    async def mark_dirty(self, conn: Any, month: date) -> None:
        self.dirty.append(month)


@pytest.mark.asyncio
async def test_preview_writes_nothing_and_confirm_applies(api, auth_headers, ofx_account, pool):
    import main  # noqa: F401 — registra adapters e hooks

    acc, number = ofx_account
    fitids = [uuid.uuid4().hex for _ in range(3)]
    r = await _preview(api, auth_headers, [("nubank.ofx", _ofx(number, fitids))])
    assert r.status_code == 200, r.text
    body = r.json()
    f = body["files"][0]
    assert (f["source"], f["account_id"], f["new"], f["existing"], f["skipped"]) == (
        "nubank_ofx",
        acc,
        3,
        0,
        0,
    )
    assert (f["period_start"], f["period_end"]) == ("2099-01-05", "2099-01-05")
    assert await _count(pool, acc) == 0  # prévia não grava
    async with pool.acquire() as conn:
        staged = await conn.fetchrow(
            "SELECT status, plan_hash, expires_at - created_at AS ttl FROM import_batches "
            "WHERE id = $1::uuid",
            body["batch_id"],
        )
    assert staged["status"] == "staged" and staged["plan_hash"] == body["hash"]
    assert staged["ttl"].total_seconds() == 24 * 3600

    port = RecordingPort()
    register_month_status(port)
    try:
        c = await api.post(
            f"{URL}/confirm",
            json={"batch_id": body["batch_id"], "hash": body["hash"]},
            headers=auth_headers,
        )
    finally:
        register_month_status(AllMonthsOpen())
    assert c.status_code == 200, c.text
    assert c.json()["imported"] == 3
    assert date(2099, 1, 1) in port.dirty
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT batch_id::text, source, review_status FROM transactions WHERE account_id = $1",
            uuid.UUID(acc),
        )
        files = await conn.fetch(
            "SELECT source, file_hash, account_id::text FROM import_batch_files "
            "WHERE batch_id = $1",
            uuid.UUID(body["batch_id"]),
        )
        status = await conn.fetchval(
            "SELECT status FROM import_batches WHERE id = $1::uuid", body["batch_id"]
        )
    assert {(r["batch_id"], r["source"], r["review_status"]) for r in rows} == {
        (body["batch_id"], "nubank_ofx", "pending")
    }
    assert status == "applied"
    assert [(x["source"], x["account_id"]) for x in files] == [("nubank_ofx", acc)]
    assert files[0]["file_hash"] == f["file_hash"]

    again = await api.post(
        f"{URL}/confirm",
        json={"batch_id": body["batch_id"], "hash": body["hash"]},
        headers=auth_headers,
    )
    assert again.status_code == 409  # duplo clique: o lote já está applied
    assert await _count(pool, acc) == 3

    # o mesmo arquivo de novo: 0 novas e aviso "arquivo já importado"
    r2 = await _preview(api, auth_headers, [("nubank.ofx", _ofx(number, fitids))])
    f2 = r2.json()["files"][0]
    assert (f2["new"], f2["existing"], f2["already_imported"]) == (0, 3, True)
    async with pool.acquire() as conn:
        alerts = await alerts_service.active_alerts(conn)
    assert any(
        a.message == "Arquivo já importado: nubank.ofx. 0 transações novas." for a in alerts.items
    )


@pytest.mark.asyncio
async def test_confirm_refuses_wrong_hash_and_stale_plan(api, auth_headers, ofx_account, pool):
    import main  # noqa: F401

    acc, number = ofx_account
    fitids = [uuid.uuid4().hex for _ in range(2)]
    body = (await _preview(api, auth_headers, [("a.ofx", _ofx(number, fitids))])).json()
    bad = await api.post(
        f"{URL}/confirm",
        json={"batch_id": body["batch_id"], "hash": "0" * 64},
        headers=auth_headers,
    )
    assert bad.status_code == 409
    # outra prévia aplicada antes desta: o plano mudou, o hash não bate mais
    other = (await _preview(api, auth_headers, [("b.ofx", _ofx(number, fitids[:1]))])).json()
    ok = await api.post(
        f"{URL}/confirm",
        json={"batch_id": other["batch_id"], "hash": other["hash"]},
        headers=auth_headers,
    )
    assert ok.status_code == 200
    stale = await api.post(
        f"{URL}/confirm",
        json={"batch_id": body["batch_id"], "hash": body["hash"]},
        headers=auth_headers,
    )
    assert stale.status_code == 409 and stale.json()["detail"]["error"] == "previa_desatualizada"
    assert await _count(pool, acc) == 1
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE import_batches SET expires_at = now() - interval '1 minute' "
            "WHERE id = $1::uuid",
            body["batch_id"],
        )
    expired = await api.post(
        f"{URL}/confirm",
        json={"batch_id": body["batch_id"], "hash": body["hash"]},
        headers=auth_headers,
    )
    assert expired.status_code == 409


@pytest.mark.asyncio
async def test_csv_needs_account_and_override_writes_to_it(api, auth_headers, account, pool):
    import main  # noqa: F401

    fitids = [uuid.uuid4().hex for _ in range(2)]
    first = (await _preview(api, auth_headers, [("extrato.csv", _csv(fitids))])).json()
    f = first["files"][0]
    assert f["source"] == "nubank_csv" and f["needs"] == ["account"]
    blocked = await api.post(
        f"{URL}/confirm",
        json={"batch_id": first["batch_id"], "hash": first["hash"]},
        headers=auth_headers,
    )
    assert blocked.status_code == 422

    re = await api.post(
        f"{URL}/replan",
        json={
            "batch_id": first["batch_id"],
            "overrides": {f["file_hash"]: {"account_id": account}},
        },
        headers=auth_headers,
    )
    assert re.status_code == 200, re.text
    second = re.json()
    assert second["batch_id"] != first["batch_id"] and second["hash"] != first["hash"]
    g = second["files"][0]
    assert (g["account_id"], g["new"], g["needs"]) == (account, 2, [])
    c = await api.post(
        f"{URL}/confirm",
        json={"batch_id": second["batch_id"], "hash": second["hash"]},
        headers=auth_headers,
    )
    assert c.status_code == 200
    assert await _count(pool, account) == 2
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1::uuid", account)
        await conn.execute(
            "DELETE FROM import_batches WHERE id = ANY($1::uuid[])",
            [first["batch_id"], second["batch_id"]],
        )


@pytest.mark.asyncio
async def test_unknown_format_is_refused_on_its_line(api, auth_headers):
    import main  # noqa: F401

    r = await _preview(api, auth_headers, [("notas.txt", b"qualquer coisa")])
    assert r.status_code == 200
    f = r.json()["files"][0]
    assert f["source"] is None and f["error"] == "Formato não reconhecido."


def test_adapter_registry_has_nubank() -> None:
    import main  # noqa: F401

    assert {"nubank_ofx", "nubank_csv"} <= set(ingest_service.registered_sources())
