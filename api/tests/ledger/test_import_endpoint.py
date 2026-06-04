"""Endpoint de import Nubank (STORY-01-13-14) — upload por corpo cru, idempotente."""

import uuid


def _csv() -> tuple[str, list[str]]:
    fids = [uuid.uuid4().hex for _ in range(3)]
    body = (
        "Data,Valor,Identificador,Descrição\n"
        f"01/01/2099,1000.00,{fids[0]},Salário recebido\n"
        f"02/01/2099,-200.00,{fids[1]},Pagamento de boleto\n"
        f"03/01/2099,-2130.00,{fids[2]},Aplicação RDB\n"
    )
    return body, fids


async def test_import_requires_auth(api):
    resp = await api.post(f"/api/v1/ledger/import?account_id={uuid.uuid4()}", content="x")
    assert resp.status_code == 401


async def test_import_unknown_account(api, auth_headers):
    resp = await api.post(
        f"/api/v1/ledger/import?account_id={uuid.uuid4()}&filename=x.csv",
        content=_csv()[0],
        headers={**auth_headers, "Content-Type": "text/csv"},
    )
    assert resp.status_code == 404


async def test_import_empty_returns_422(api, auth_headers, account):
    resp = await api.post(
        f"/api/v1/ledger/import?account_id={account}&filename=x.csv",
        content="Data,Valor,Identificador,Descrição\n",
        headers={**auth_headers, "Content-Type": "text/csv"},
    )
    assert resp.status_code == 422


async def test_import_csv_classifies_and_dedups(api, auth_headers, account):
    body, _ = _csv()
    first = await api.post(
        f"/api/v1/ledger/import?account_id={account}&filename=nubank.csv",
        content=body,
        headers={**auth_headers, "Content-Type": "text/csv"},
    )
    assert first.status_code == 200
    r = first.json()
    assert r["parsed"] == 3
    assert r["imported"] == 2  # receita + despesa
    assert r["skipped"] == 1  # Aplicação RDB (investimento, fora do caixa)
    assert r["duplicates"] == 0

    # idempotência: reimportar o mesmo arquivo não duplica
    again = await api.post(
        f"/api/v1/ledger/import?account_id={account}&filename=nubank.csv",
        content=body,
        headers={**auth_headers, "Content-Type": "text/csv"},
    )
    r2 = again.json()
    assert r2["imported"] == 0
    assert r2["duplicates"] == 2
    assert r2["skipped"] == 1

    # só receita+despesa viraram transações (investimento foi excluído)
    listed = await api.get(f"/api/v1/transactions?account_id={account}", headers=auth_headers)
    assert listed.json()["total"] == 2
