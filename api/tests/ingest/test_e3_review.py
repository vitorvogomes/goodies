"""Achados do code review do Épico 3 — cada teste trava um defeito corrigido."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.ledger import service as ledger_service
from tests.ingest.test_b3 import _POS, _xlsx
from tests.ingest.test_protocol import _preview

URL = "/api/v1/ingest"


def _letters() -> str:
    return "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])


def _ofx(acctid: str, rows: list[tuple[str, str, str]], bal: str, asof: str) -> bytes:
    body = "".join(
        f"<STMTTRN><TRNTYPE>X</TRNTYPE><DTPOSTED>{d}000000[-3:BRT]</DTPOSTED>"
        f"<TRNAMT>{a}</TRNAMT><FITID>{uuid.uuid4().hex}</FITID><MEMO>{m}</MEMO></STMTTRN>\n"
        for d, a, m in rows
    )
    return (
        "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        f"<BANKACCTFROM><ACCTID>{acctid}</ACCTID></BANKACCTFROM>\n<BANKTRANLIST>\n{body}"
        f"</BANKTRANLIST>\n<LEDGERBAL>\n<BALAMT>{bal}</BALAMT>\n<DTASOF>{asof}000000</DTASOF>\n"
        "</LEDGERBAL>\n</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode()


async def _apply(api, headers, files) -> dict[str, Any]:
    body = (await _preview(api, headers, files)).json()
    r = await api.post(
        f"{URL}/confirm", json={"batch_id": body["batch_id"], "hash": body["hash"]}, headers=headers
    )
    assert r.status_code == 200, r.text
    return {**body, "confirmed": r.json()}


async def _consumo(pool, skip: int = 0) -> str:
    async with pool.acquire() as conn:
        return str(
            await conn.fetchval(
                "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                "WHERE c.role = 'consumo' AND NOT g.is_system AND c.is_active "
                "ORDER BY c.key OFFSET $1 LIMIT 1",
                skip,
            )
        )


@pytest.mark.asyncio
async def test_new_short_rule_does_not_beat_a_longer_one(api, auth_headers, ofx_account, pool):
    _, number = ofx_account
    w = _letters()
    a, b = await _consumo(pool, 0), await _consumo(pool, 1)
    try:
        long = await api.post(
            "/api/v1/ledger/rules",
            json={"pattern": f"zq{w} eats", "direction": "saida", "category_id": a},
            headers=auth_headers,
        )
        assert long.status_code == 201
        await _apply(
            api,
            auth_headers,
            [("x.ofx", _ofx(number, [("20990201", "-9", f"ZQ{w} EATS pedido")], "1", "20990228"))],
        )
        short = await api.post(
            "/api/v1/ledger/rules",
            json={"pattern": f"zq{w}", "direction": "saida", "category_id": b},
            headers=auth_headers,
        )
        assert short.status_code == 201 and short.json()["applied"] == 0
        async with pool.acquire() as conn:
            cat = await conn.fetchval(
                "SELECT category_id::text FROM transactions WHERE description = $1",
                f"ZQ{w} EATS pedido",
            )
        assert cat == a
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM category_rules WHERE pattern LIKE $1", f"zq{w}%")


@pytest.mark.asyncio
async def test_deleting_a_transaction_removes_its_derived_operation(
    api, auth_headers, account, pool
):
    import main  # noqa: F401

    async with pool.acquire() as conn:
        cx = str(await conn.fetchval("SELECT id FROM categories WHERE key = 'invest:caixinha_rdb'"))
    tx = await api.post(
        "/api/v1/ledger/transactions",
        json={
            "account_id": account,
            "date": "2099-04-02",
            "amount": f"-{uuid.uuid4().int % 9000 + 1000}.37",
            "description": "Aplicação caixinha Turbo",
            "category_id": cx,
        },
        headers=auth_headers,
    )
    assert tx.status_code == 201, tx.text
    tid = tx.json()["id"]
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE transaction_id = $1::uuid", tid
            )
            == 1
        )
    gone = await api.delete(f"/api/v1/ledger/transactions/{tid}", headers=auth_headers)
    assert gone.status_code == 204, gone.text
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE transaction_id = $1::uuid", tid
            )
            == 0
        )


@pytest.mark.asyncio
async def test_undo_recomputes_anchor_without_the_batch(api, auth_headers, ofx_account, pool):
    import main  # noqa: F401

    acc, number = ofx_account
    await _apply(
        api, auth_headers, [("fev.ofx", _ofx(number, [("20990210", "-20", "a")], "80", "20990228"))]
    )
    jan = await _apply(
        api,
        auth_headers,
        [("jan.ofx", _ofx(number, [("20990110", "-10", "b")], "100", "20990131"))],
    )
    async with pool.acquire() as conn:
        await ledger_service.recompute_anchor(conn, uuid.UUID(acc))
        assert await conn.fetchval(
            "SELECT opening_balance_date FROM accounts WHERE id = $1::uuid", acc
        ) == date(2099, 1, 31)
    r = await api.post(f"{URL}/batches/{jan['batch_id']}/undo", headers=auth_headers)
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT opening_balance, opening_balance_date FROM accounts WHERE id = $1::uuid", acc
        )
        await conn.execute("DELETE FROM account_balances WHERE account_id = $1::uuid", acc)
    # fev: 80 − (−20) = 100 (a transação de jan saiu com o lote)
    assert (row["opening_balance_date"], row["opening_balance"]) == (
        date(2099, 2, 28),
        Decimal("100.00"),
    )


@pytest.mark.asyncio
async def test_confirm_with_nothing_new_leaves_no_batch(api, auth_headers, ofx_account, pool):
    import main  # noqa: F401

    _, number = ofx_account
    content = _ofx(number, [("20990301", "-3", "c")], "5", "20990331")
    await _apply(api, auth_headers, [("m.ofx", content)])
    before = (await api.get(f"{URL}/batches", headers=auth_headers)).json()["items"][0]["id"]
    again = await _apply(api, auth_headers, [("m.ofx", content)])
    assert again["confirmed"]["imported"] == 0
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM import_batches WHERE id = $1::uuid", again["batch_id"]
            )
            == 0
        )
        await conn.execute(
            "DELETE FROM account_balances b USING accounts a "
            "WHERE a.id = b.account_id AND a.account_number = $1",
            number,
        )
    assert (await api.get(f"{URL}/batches", headers=auth_headers)).json()["items"][0][
        "id"
    ] == before


@pytest.mark.asyncio
async def test_malformed_batch_id_and_replan_drops_previous(api, auth_headers, account, pool):
    import main  # noqa: F401

    bad = await api.post(
        f"{URL}/confirm", json={"batch_id": "abc", "hash": "x"}, headers=auth_headers
    )
    assert bad.status_code == 422
    csv = (
        b"Data,Valor,Identificador,Descri\xc3\xa7\xc3\xa3o\n01/02/2099,-1.00,"
        + uuid.uuid4().hex.encode()
        + b",x\n"
    )
    first = (await _preview(api, auth_headers, [("e.csv", csv)])).json()
    re = await api.post(
        f"{URL}/replan",
        json={
            "batch_id": first["batch_id"],
            "overrides": {first["files"][0]["file_hash"]: {"account_id": account}},
        },
        headers=auth_headers,
    )
    assert re.status_code == 200
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM import_batches WHERE id = $1::uuid", first["batch_id"]
            )
            == 0
        )
        await conn.execute("DELETE FROM import_batches WHERE id = $1::uuid", re.json()["batch_id"])


@pytest.mark.asyncio
async def test_undo_consolidado_restores_previous_price(api, auth_headers, pool, monkeypatch):
    import main  # noqa: F401
    from engines.market import service as market_service

    t = f"ZE{uuid.uuid4().hex[:2].upper()}3"
    try:
        ago = _xlsx({"Posição - Ações": [_POS, (f"{t} - X", t, 7, 10.0, 70.0)]})
        set_ = _xlsx({"Posição - Ações": [_POS, (f"{t} - X", t, 7, 12.0, 84.0)]})
        await _apply(api, auth_headers, [("relatorio-consolidado-mensal-2099-agosto.xlsx", ago)])
        last = await _apply(
            api, auth_headers, [("relatorio-consolidado-mensal-2099-setembro.xlsx", set_)]
        )
        async with pool.acquire() as conn:
            assert (
                float(
                    await conn.fetchval("SELECT price_brl FROM asset_prices WHERE ticker = $1", t)
                )
                == 12.0
            )
        pv = (
            await api.post(f"{URL}/batches/{last['batch_id']}/undo/preview", headers=auth_headers)
        ).json()
        assert pv["prices"] == 1
        # O cache só se invalida com o preço de volta já commitado (uma leitura concorrente
        # que recacheie vê o preço anterior, não o desfeito).
        seen: list[float] = []
        real = market_service.invalidate_price_cache

        async def spy(ticker: str) -> None:
            async with pool.acquire() as other:
                seen.append(
                    float(
                        await other.fetchval(
                            "SELECT price_brl FROM asset_prices WHERE ticker = $1", ticker
                        )
                    )
                )
            await real(ticker)

        monkeypatch.setattr(market_service, "invalidate_price_cache", spy)
        r = await api.post(f"{URL}/batches/{last['batch_id']}/undo", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert seen == [10.0]
        async with pool.acquire() as conn:
            assert (
                float(
                    await conn.fetchval("SELECT price_brl FROM asset_prices WHERE ticker = $1", t)
                )
                == 10.0
            )
            # O dia do consolidado desfeito sai do histórico; o anterior fica.
            history = {
                r["ref_date"]: float(r["price_brl"])
                for r in await conn.fetch(
                    "SELECT ref_date, price_brl FROM asset_price_history WHERE ticker = $1", t
                )
            }
            assert history == {date(2099, 8, 31): 10.0}
    finally:
        async with pool.acquire() as conn:
            batches = [
                r["batch_id"]
                for r in await conn.fetch(
                    "SELECT DISTINCT s.batch_id FROM broker_position_snapshots s "
                    "JOIN assets a ON a.id = s.asset_id WHERE a.key = $1",
                    f"b3:{t}",
                )
            ]
            await conn.execute(
                "DELETE FROM broker_position_snapshots s USING assets a "
                "WHERE a.id = s.asset_id AND a.key = $1",
                f"b3:{t}",
            )
            await conn.execute("DELETE FROM import_batches WHERE id = ANY($1::uuid[])", batches)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", t)
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", t)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{t}")


@pytest.mark.asyncio
async def test_nubank_period_comes_from_the_file_name(api, auth_headers, account):
    import main  # noqa: F401

    csv = (
        b"Data,Valor,Identificador,Descri\xc3\xa7\xc3\xa3o\n05/03/2099,-1.00,"
        + uuid.uuid4().hex.encode()
        + b",x\n"
    )
    body = (await _preview(api, auth_headers, [("NU_123456_01MAR2099_31MAR2099.csv", csv)])).json()
    f = body["files"][0]
    assert (f["period_start"], f["period_end"]) == ("2099-03-01", "2099-03-31")
