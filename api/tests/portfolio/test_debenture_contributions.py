"""Integralizações da debênture editáveis (P17): a lista vem das operações do ativo (as que valoram
a debênture pela taxa); dá para incluir, corrigir data/valor e excluir a que não tem transação."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

URL = "/api/v1/portfolio/debentures"


async def _cleanup(pool: Any, debenture: str) -> None:
    async with pool.acquire() as conn:
        asset = await conn.fetchval(
            "SELECT asset_id FROM debentures WHERE id = $1::uuid", debenture
        )
        await conn.execute("DELETE FROM asset_operations WHERE asset_id = $1", asset)
        await conn.execute("DELETE FROM debentures WHERE id = $1::uuid", debenture)
        await conn.execute(
            "DELETE FROM asset_prices WHERE ticker = (SELECT price_ref FROM assets WHERE id = $1)",
            asset,
        )
        await conn.execute("DELETE FROM assets WHERE id = $1", asset)


@pytest.mark.asyncio
async def test_contributions_crud(api: Any, auth_headers: dict, pool: Any) -> None:
    r = await api.post(
        URL,
        json={
            "issuer": "EmissorInteg",
            "rate_label": "Pré 24% a.a.",
            "monthly_factor": "1.78",
            "start_date": "2020-07-01",
            "maturity_date": "2023-06-16",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    deb = r.json()
    try:
        for day in ("2020-07-01", "2020-08-01"):
            add = await api.post(
                f"{URL}/{deb['id']}/contributions",
                json={"data": day, "valor": "1000.00"},
                headers=auth_headers,
            )
            assert add.status_code == 201, add.text
        rows = (await api.get(f"{URL}/{deb['id']}/contributions", headers=auth_headers)).json()
        assert [(x["data"], x["valor"]) for x in rows] == [
            ("2020-08-01", 1000.0),
            ("2020-07-01", 1000.0),
        ]  # mais recente primeiro
        assert all(x["transacao"] is None for x in rows)
        first = rows[1]
        fix = await api.patch(
            f"{URL}/{deb['id']}/contributions/{first['id']}",
            json={"data": "2020-07-02", "valor": "1200.00"},
            headers=auth_headers,
        )
        assert fix.status_code == 200, fix.text
        assert (fix.json()["data"], fix.json()["valor"]) == ("2020-07-02", 1200.0)
        listed = (await api.get(URL, headers=auth_headers)).json()
        assert Decimal(str(next(d for d in listed if d["id"] == deb["id"])["aplicado"])) == Decimal(
            "2200"
        )
        gone = await api.delete(
            f"{URL}/{deb['id']}/contributions/{rows[0]['id']}", headers=auth_headers
        )
        assert gone.status_code == 204
        rows = (await api.get(f"{URL}/{deb['id']}/contributions", headers=auth_headers)).json()
        assert len(rows) == 1
        bad = await api.post(
            f"{URL}/{deb['id']}/contributions",
            json={"data": "2020-09-01", "valor": "0"},
            headers=auth_headers,
        )
        assert bad.status_code == 422
    finally:
        await _cleanup(pool, deb["id"])
