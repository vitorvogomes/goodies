"""Story 8.2 — metas de alocação: `portfolio_targets` de `planning` com banda, piso e vigência; cada
nível soma 100% (a prévia da API, nunca o navegador); salvar grava a versão do mês atual."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.planning.targets import TargetsIn, check_sums

URL = "/api/v1/planning/targets"
D = Decimal
CLASSES = ["acoes_br", "etfs", "fiis", "renda_fixa", "aposentadoria", "cripto"]


def _body(
    pcts: list[str], assets: dict[str, list[tuple[str, str]]] | None = None
) -> dict[str, Any]:
    return {
        "classes": [
            {
                "cls": c,
                "pct": p,
                "band_pp": "5",
                "floor": "100.00" if c == "renda_fixa" else "0",
                "assets": [{"asset_id": a, "pct": x} for a, x in (assets or {}).get(c, [])],
            }
            for c, p in zip(CLASSES, pcts, strict=True)
        ]
    }


def test_each_level_sums_100() -> None:
    ok = TargetsIn.model_validate(_body(["10", "12.5", "10", "50", "12.5", "5"]))
    assert check_sums(ok) == []
    off = check_sums(TargetsIn.model_validate(_body(["10", "12.5", "10", "45", "12.5", "5"])))
    assert [(e.level, e.message) for e in off] == [("classes", "Soma em 95%. Ajuste para 100%.")]
    assets = {"fiis": [("a", "60"), ("b", "30.5")]}
    level = check_sums(
        TargetsIn.model_validate(_body(["10", "12.5", "10", "50", "12.5", "5"], assets))
    )
    assert [(e.level, e.message) for e in level] == [("fiis", "Soma em 90,5%. Ajuste para 100%.")]
    zero = {"fiis": [("a", "0"), ("b", "0")]}  # sem meta por ativo: o nível não conta
    assert (
        check_sums(TargetsIn.model_validate(_body(["10", "12.5", "10", "50", "12.5", "5"], zero)))
        == []
    )


@pytest.mark.asyncio
async def test_preview_save_and_v1_allocation(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    month = today_brt().replace(day=1)
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        before = await conn.fetch(
            "SELECT id, valid_to FROM portfolio_targets WHERE user_id = $1::uuid", owner
        )
    try:
        bad = await api.post(
            f"{URL}/preview", json=_body(["10", "10", "10", "50", "10", "5"]), headers=auth_headers
        )
        assert bad.status_code == 200
        assert bad.json() == {
            "ok": False,
            "errors": [
                {"level": "classes", "total": 95.0, "message": "Soma em 95%. Ajuste para 100%."}
            ],
        }
        refused = await api.put(
            URL, json=_body(["10", "10", "10", "50", "10", "5"]), headers=auth_headers
        )
        assert refused.status_code == 422 and refused.json()["detail"]["error"] == "metas_invalidas"
        current = (await api.get(URL, headers=auth_headers)).json()
        fii = next(c for c in current["classes"] if c["cls"] == "fiis")
        picks = [a["asset_id"] for a in fii["assets"][:2]]
        assets = {"fiis": [(picks[0], "70"), (picks[1], "30")]} if len(picks) == 2 else None
        r = await api.put(
            URL, json=_body(["15", "10", "10", "50", "10", "5"], assets), headers=auth_headers
        )
        assert r.status_code == 200, r.text
        saved = r.json()
        assert saved["defined"] is True and saved["valid_from"] == month.isoformat()
        by_cls = {c["cls"]: c for c in saved["classes"]}
        assert (by_cls["acoes_br"]["pct"], by_cls["renda_fixa"]["floor"]) == (15.0, 100.0)
        if assets:
            got = {a["asset_id"]: a["pct"] for a in by_cls["fiis"]["assets"]}
            assert (got[picks[0]], got[picks[1]]) == (70.0, 30.0)
        again = await api.put(
            URL, json=_body(["20", "10", "10", "45", "10", "5"]), headers=auth_headers
        )
        assert again.status_code == 200  # no mesmo mês, substitui a versão do mês
        async with pool.acquire() as conn:
            versions = await conn.fetchval(
                "SELECT count(*) FROM portfolio_targets WHERE user_id = $1::uuid "
                "AND valid_from = $2 AND asset_id IS NULL",
                owner,
                month,
            )
        assert versions == 6
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM portfolio_targets WHERE user_id = $1::uuid AND valid_from = $2",
                owner,
                month,
            )
            for row in before:
                await conn.execute(
                    "UPDATE portfolio_targets SET valid_to = $2 WHERE id = $1",
                    row["id"],
                    row["valid_to"],
                )
