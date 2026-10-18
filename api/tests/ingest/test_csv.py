"""Story 3.7 — CSV do Nubank: pede a conta, avisa que não confere saldo; depois de aplicado, o aviso
"CSV importado sem conferência" fica até um OFX da conta cobrir o período; formato desconhecido é
recusado só na linha dele."""

from __future__ import annotations

import uuid

import pytest

from engines.alerts import service as alerts_service
from tests.ingest.test_protocol import _csv, _ofx, _preview

URL = "/api/v1/ingest"
UNKNOWN = (
    "Formato não reconhecido. Aceitos: OFX Nubank, CSV Nubank, B3 movimentação e consolidado "
    "(.xlsx)."
)
CSV_ALERT = "CSV importado sem conferência de saldo. Só o OFX permite conferir."


async def _confirm(api, headers, body):
    r = await api.post(
        f"{URL}/confirm", json={"batch_id": body["batch_id"], "hash": body["hash"]}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _alerts(pool):
    async with pool.acquire() as conn:
        return [a for a in (await alerts_service.active_alerts(conn)).items]


@pytest.mark.asyncio
async def test_csv_flow(api, auth_headers, ofx_account, pool) -> None:
    import main  # noqa: F401

    acc, number = ofx_account
    fitids = [uuid.uuid4().hex for _ in range(2)]
    first = (
        await _preview(api, auth_headers, [("extrato.csv", _csv(fitids)), ("notas.txt", b"x")])
    ).json()
    csv_line, unknown = first["files"]
    assert csv_line["needs"] == ["account"]
    assert csv_line["warnings"] == ["CSV não permite conferir o saldo. Prefira o OFX."]
    assert unknown["error"] == UNKNOWN and unknown["source"] is None
    re = await api.post(
        f"{URL}/replan",
        json={
            "batch_id": first["batch_id"],
            "overrides": {csv_line["file_hash"]: {"account_id": acc}},
        },
        headers=auth_headers,
    )
    second = re.json()
    assert second["files"][0]["new"] == 2  # o desconhecido não trava o outro
    await _confirm(api, auth_headers, second)
    mine = [a for a in await _alerts(pool) if a.key == f"csv_sem_conferencia:{acc}"]
    assert [a.message for a in mine] == [CSV_ALERT]
    assert mine[0].action.label == "Importar OFX"
    # reimport do mesmo CSV: deduplicado
    again = (await _preview(api, auth_headers, [("extrato.csv", _csv(fitids))])).json()
    re2 = await api.post(
        f"{URL}/replan",
        json={
            "batch_id": again["batch_id"],
            "overrides": {again["files"][0]["file_hash"]: {"account_id": acc}},
        },
        headers=auth_headers,
    )
    assert (re2.json()["files"][0]["new"], re2.json()["files"][0]["existing"]) == (0, 2)

    # um OFX da conta cobrindo o período tira o aviso
    ofx = (
        await _preview(
            api, auth_headers, [("nu.ofx", _ofx(number, [uuid.uuid4().hex], "20990228"))]
        )
    ).json()
    await _confirm(api, auth_headers, ofx)
    assert not [a for a in await _alerts(pool) if a.key == f"csv_sem_conferencia:{acc}"]
