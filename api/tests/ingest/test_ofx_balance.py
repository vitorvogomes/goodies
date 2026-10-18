"""Story 3.4 — OFX completo: saldo informado (LEDGERBAL) na prévia, em `import_batch_files` e em
`account_balances`; reimport com 0 novas ainda grava o saldo; OFX do MEI com vários meses;
pagador."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tests.ingest.test_protocol import _preview

URL = "/api/v1/ingest"


def _ofx(acctid: str, rows: list[tuple[str, str, str, str]], bal: str, asof: str) -> bytes:
    body = "".join(
        f"<STMTTRN><TRNTYPE>X</TRNTYPE><DTPOSTED>{d}000000[-3:BRT]</DTPOSTED>"
        f"<TRNAMT>{amt}</TRNAMT><FITID>{fid}</FITID><MEMO>{memo}</MEMO></STMTTRN>\n"
        for d, amt, fid, memo in rows
    )
    return (
        "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        f"<BANKACCTFROM><ACCTID>{acctid}</ACCTID></BANKACCTFROM>\n<BANKTRANLIST>\n{body}"
        f"</BANKTRANLIST>\n<LEDGERBAL>\n<BALAMT>{bal}</BALAMT>\n"
        f"<DTASOF>{asof}000000[-3:BRT]</DTASOF>\n</LEDGERBAL>\n"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode()


@pytest.mark.asyncio
async def test_balance_payer_and_multi_month(api, auth_headers, ofx_account, pool) -> None:
    import main  # noqa: F401

    acc, number = ofx_account
    rows = [
        (
            "20990115",
            "1500.00",
            uuid.uuid4().hex,
            "Transferência recebida pelo Pix - ACME LTDA - 12.345.678/0001-90 - Banco",
        ),
        ("20990320", "-40.00", uuid.uuid4().hex, "Pagamento de boleto efetuado"),
    ]
    body = (
        await _preview(api, auth_headers, [("mei.ofx", _ofx(number, rows, "1460.00", "20990331"))])
    ).json()
    f = body["files"][0]
    assert (f["period_start"], f["period_end"], f["new"]) == ("2099-01-15", "2099-03-20", 2)
    assert (f["reported_balance"], f["reported_balance_date"]) == (1460.0, "2099-03-31")
    c = await api.post(
        f"{URL}/confirm",
        json={"batch_id": body["batch_id"], "hash": body["hash"]},
        headers=auth_headers,
    )
    assert c.status_code == 200, c.text
    async with pool.acquire() as conn:
        payers = dict(
            await conn.fetch(
                "SELECT description, payer FROM transactions WHERE account_id = $1::uuid", acc
            )
        )
        balances = await conn.fetch(
            "SELECT as_of, balance, batch_id::text FROM account_balances "
            "WHERE account_id = $1::uuid",
            acc,
        )
        file_balance = await conn.fetchval(
            "SELECT reported_balance FROM import_batch_files WHERE batch_id = $1::uuid",
            body["batch_id"],
        )
    assert payers[rows[0][3]] == "ACME LTDA" and payers[rows[1][3]] is None
    assert [(str(b["as_of"]), b["balance"], b["batch_id"]) for b in balances] == [
        ("2099-03-31", Decimal("1460.00"), body["batch_id"])
    ]
    assert file_balance == Decimal("1460.00")

    # reimport com 0 novas e saldo de outra data: ainda grava o saldo informado
    again = (
        await _preview(api, auth_headers, [("mei2.ofx", _ofx(number, rows, "1460.00", "20990405"))])
    ).json()
    assert again["files"][0]["new"] == 0
    c2 = await api.post(
        f"{URL}/confirm",
        json={"batch_id": again["batch_id"], "hash": again["hash"]},
        headers=auth_headers,
    )
    assert c2.status_code == 200
    async with pool.acquire() as conn:
        dates = [
            str(r["as_of"])
            for r in await conn.fetch(
                "SELECT as_of FROM account_balances WHERE account_id = $1::uuid ORDER BY 1", acc
            )
        ]
        await conn.execute("DELETE FROM account_balances WHERE account_id = $1::uuid", acc)
        await conn.execute("DELETE FROM import_batches WHERE id = $1::uuid", again["batch_id"])
    assert dates == ["2099-03-31", "2099-04-05"]
