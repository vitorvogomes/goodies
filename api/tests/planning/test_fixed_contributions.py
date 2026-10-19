"""Aportes fixos do mês (pedido de 18/10/2026): a Flash integraliza R$ 1.000 e a caixinha da Ana
Maria recebe R$ 4.000 todo mês. Viram travas padrão na Distribuição (a trava do mês vence); ativo
fixo numa classe sem meta por ativo leva a classe inteira ao valor fixo; excluir fecha a
vigência."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt

D = Decimal
URL = "/api/v1/planning/fixed-contributions"
PREVIEW = "/api/v1/planning/distribution/preview"


@pytest.mark.asyncio
async def test_fixed_goal_and_asset_drive_the_distribution(api: Any, auth_headers: Any, pool: Any):
    import main  # noqa: F401

    mes = today_brt().strftime("%Y-%m")
    tag = uuid.uuid4().hex[:6]
    async with pool.acquire() as conn:
        goal = str(
            await conn.fetchval(
                "INSERT INTO goals (name, target, deadline) VALUES ($1, 100000, '2099-01-01') "
                "RETURNING id",
                f"Fixo {tag}",
            )
        )
        asset = str(
            await conn.fetchval(
                "INSERT INTO assets (key, name, class, valuation) VALUES ($1, $2, 'renda_fixa', "
                "'manual') RETURNING id",
                f"debenture:fixo-{tag}",
                f"Fixa {tag}",
            )
        )
    try:
        bad = await api.put(URL, json={"key": "goal:x", "amount": "1"}, headers=auth_headers)
        assert bad.status_code == 422
        ghost = await api.put(
            URL, json={"key": f"goal:{uuid.uuid4()}", "amount": "1"}, headers=auth_headers
        )
        assert ghost.status_code == 422
        r = await api.put(URL, json={"key": f"goal:{goal}", "amount": "4000"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        r = await api.put(
            URL, json={"key": f"asset:{asset}", "amount": "1000"}, headers=auth_headers
        )
        body = r.json()
        items = {i["key"]: i for i in body["items"]}
        assert items[f"goal:{goal}"]["amount"] == 4000.0
        assert items[f"goal:{goal}"]["label"] == f"Fixo {tag}"
        assert any(o["key"] == f"asset:{asset}" for o in body["options"])
        # salvar de novo troca o valor (uma versão ativa por chave)
        await api.put(URL, json={"key": f"goal:{goal}", "amount": "4000"}, headers=auth_headers)
        listed = (await api.get(URL, headers=auth_headers)).json()["items"]
        assert sum(1 for i in listed if i["key"] == f"goal:{goal}") == 1

        dist = (
            await api.post(PREVIEW, json={"mes": mes, "planejado": "20000"}, headers=auth_headers)
        ).json()
        g = next(x for x in dist["goals"] if x["id"] == goal)
        assert g["sugerido"] == 4000.0 and g["fixo"] and g["locked"]
        rf = next((c for c in dist["classes"] if c["cls"] == "renda_fixa"), None)
        if rf is not None and not any(
            (a["meta"] or 0) > 0 for a in rf["assets"]
        ):  # classe sem meta por ativo: recebe só os fixos
            line = next(a for a in rf["assets"] if a["id"] == asset)
            assert line["sugerido"] == 1000.0 and line["fixo"]
            assert rf["fixo"] and rf["sugerido"] >= 1000.0

        # a trava do próprio mês vence o fixo
        put = await api.put(
            f"/api/v1/planning/months/{mes}/travas/goal:{goal}",
            json={"valor": "1500.00"},
            headers=auth_headers,
        )
        assert put.status_code == 200
        dist = (
            await api.post(PREVIEW, json={"mes": mes, "planejado": "20000"}, headers=auth_headers)
        ).json()
        g = next(x for x in dist["goals"] if x["id"] == goal)
        assert g["sugerido"] == 1500.0 and not g["fixo"]
        await api.delete(f"/api/v1/planning/months/{mes}/travas/goal:{goal}", headers=auth_headers)

        assert (await api.delete(f"{URL}/goal:{goal}", headers=auth_headers)).status_code == 204
        assert (await api.delete(f"{URL}/goal:{goal}", headers=auth_headers)).status_code == 404
        listed = (await api.get(URL, headers=auth_headers)).json()["items"]
        assert all(i["key"] != f"goal:{goal}" for i in listed)
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM fixed_contributions WHERE key = ANY($1::text[])",
                [f"goal:{goal}", f"asset:{asset}"],
            )
            await conn.execute("DELETE FROM goals WHERE id = $1::uuid", goal)
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", asset)
