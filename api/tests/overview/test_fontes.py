"""Story 4.2 — Bloco Fontes do Painel (5 fontes de arquivo + as automáticas, com tipo, data e
defasagem; a de arquivo abre o Hub) e o número de transações a revisar."""

from __future__ import annotations

import pytest

from engines.common.dates import today_brt


@pytest.mark.asyncio
async def test_sources_block(api, auth_headers) -> None:
    import main  # noqa: F401

    r = await api.get("/api/v1/overview/fontes", headers=auth_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [s["key"] for s in rows] == [
        "nubank_pf",
        "nubank_mei",
        "b3_movimentacao",
        "b3_negociacao",
        "b3_consolidado",
        "precos",
        "carteiras",
        "indices",
    ]
    by = {s["key"]: s for s in rows}
    assert by["nubank_pf"]["opens_hub"] is True and by["precos"]["opens_hub"] is False
    assert (by["precos"]["label"], by["precos"]["kind"]) == ("Preços", "automático")
    assert by["indices"]["label"] == "CDI/IPCA"


@pytest.mark.asyncio
async def test_painel_counts_transactions_to_review(api, auth_headers, pool) -> None:
    async with pool.acquire() as conn:
        pending = await conn.fetchval(
            "SELECT count(*) FROM transactions WHERE review_status = 'pending'"
        )
    body = (
        await api.get(f"/api/v1/overview/painel?periodo={today_brt():%Y-%m}", headers=auth_headers)
    ).json()
    assert body["a_revisar"] == pending
