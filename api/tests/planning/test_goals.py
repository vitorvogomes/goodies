"""Story 8.1 — objetivos vinculados às caixinhas: a reserva de emergência é fixa (alvo =
multiplicador × custos fixos, horizonte editável); a caixinha ainda não ligada é sugerida e o
vínculo só vale confirmado (`goal_assets`); progresso = valor atual dos ativos vinculados, com o
aportado ao lado; o consumo financiado por resgate se divide entre objetivo e carteira."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.ledger import service as ledger_service
from engines.planning import calc

URL = "/api/v1/planning/goals"
D = Decimal


def test_financed_split_by_goal() -> None:
    assert calc.financiado_split(D(1000), D(300)) == (D(300), D(700))
    assert calc.financiado_split(D(200), D(300)) == (D(200), D(0))  # objetivo cobre primeiro
    assert calc.financiado_split(D(0), D(300)) == (D(0), D(0))


async def _caixinha(conn: Any, slug: str) -> tuple[str, str]:
    owner = await get_owner_id(conn)
    symbol = f"Nubank-{slug}"
    await conn.execute(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
        "quantidade, valor_unitario, data_operacao) VALUES ($1, 'Nubank', $2, 'Renda Fixa', "
        "'aporte', 500, 1, '2026-01-10')",
        owner,
        symbol,
    )
    asset = str(
        await conn.fetchval("SELECT asset_id FROM asset_operations WHERE asset_symbol = $1", symbol)
    )
    await conn.execute(
        "UPDATE assets SET key = $2 WHERE id = $1::uuid", asset, f"caixinha:{slug.lower()}"
    )
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ($1, 1.1, 'cdi', false) "
        "ON CONFLICT (ticker) DO UPDATE SET price_brl = 1.1",
        symbol,
    )
    return asset, symbol


async def _drop(conn: Any, assets: list[str], symbols: list[str], goals: list[str]) -> None:
    await conn.execute("DELETE FROM goal_assets WHERE asset_id = ANY($1::uuid[])", assets)
    await conn.execute("DELETE FROM goals WHERE id = ANY($1::uuid[])", goals)
    await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = ANY($1::text[])", symbols)
    await conn.execute("DELETE FROM asset_prices WHERE ticker = ANY($1::text[])", symbols)
    await conn.execute("DELETE FROM asset_aliases WHERE asset_id = ANY($1::uuid[])", assets)
    await conn.execute("DELETE FROM assets WHERE id = ANY($1::uuid[])", assets)


@pytest.mark.asyncio
async def test_reserve_is_fixed_with_target_from_fixed_costs(api, auth_headers, pool) -> None:
    async with pool.acquire() as conn:
        due = await ledger_service.fixed_costs_due(conn, today_brt().replace(day=1))
    costs = sum((r["amount"] for r in due), D(0))
    body = (await api.get(URL, headers=auth_headers)).json()
    reserve = body["goals"][0]
    assert reserve["kind"] == "reserva" and reserve["name"] == "Reserva de emergência"
    assert (reserve["multiplier"], reserve["horizon_months"]) == (6.0, 12)
    assert D(str(reserve["target"])) == (costs * 6).quantize(D("0.01"))
    r = await api.patch(
        f"{URL}/{reserve['id']}",
        json={"multiplier": "4", "horizon_months": 10},
        headers=auth_headers,
    )
    try:
        assert r.status_code == 200, r.text
        assert D(str(r.json()["target"])) == (costs * 4).quantize(D("0.01"))
        assert (await api.delete(f"{URL}/{reserve['id']}", headers=auth_headers)).status_code == 409
    finally:
        await api.patch(
            f"{URL}/{reserve['id']}",
            json={"multiplier": "6", "horizon_months": 12},
            headers=auth_headers,
        )


@pytest.mark.asyncio
async def test_suggest_confirm_dismiss_and_progress(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    tag = uuid.uuid4().hex[:4]
    trip, other = f"Trip{tag}", f"Outra{tag}"
    goals: list[str] = []
    async with pool.acquire() as conn:
        trip_asset, trip_symbol = await _caixinha(conn, trip)
        other_asset, other_symbol = await _caixinha(conn, other)
    try:
        r = await api.post(
            URL,
            json={"name": f"Viagem {trip}", "target": "5000.00", "deadline": "2027-07-31"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        goal = r.json()
        goals.append(goal["id"])
        assert goal["assets"] == [] and goal["valor"] == 0.0
        suggestions = {
            s["asset_id"]: s
            for s in (await api.get(URL, headers=auth_headers)).json()["suggestions"]
        }
        assert suggestions[trip_asset]["label"] == f"Caixinha {trip}"
        assert suggestions[trip_asset]["goal_id"] == goal["id"]  # o nome casa com o objetivo
        assert suggestions[other_asset]["goal_id"] is None
        r = await api.post(
            f"{URL}/{goal['id']}/assets", json={"asset_id": trip_asset}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        linked = r.json()
        assert [a["asset_id"] for a in linked["assets"]] == [trip_asset]
        assert (linked["valor"], linked["aportado"]) == (550.0, 500.0)  # 500 × 1,10 · aportado
        assert linked["progress"] == 11.0  # 550 / 5.000
        r = await api.post(
            f"/api/v1/planning/goal-suggestions/{other_asset}/dismiss", headers=auth_headers
        )
        assert r.status_code == 204
        after = (await api.get(URL, headers=auth_headers)).json()["suggestions"]
        assert not {s["asset_id"] for s in after} & {trip_asset, other_asset}
        bad = await api.post(
            URL, json={"name": "x", "target": "0", "deadline": "2027-01-01"}, headers=auth_headers
        )
        assert bad.status_code == 422
    finally:
        async with pool.acquire() as conn:
            await _drop(conn, [trip_asset, other_asset], [trip_symbol, other_symbol], goals)


@pytest.mark.asyncio
async def test_budget_splits_financing_by_goal(api, auth_headers) -> None:
    mes = f"{today_brt():%Y-%m}"
    body = (await api.get(f"/api/v1/closing/months/{mes}/budget", headers=auth_headers)).json()
    total = D(str(body["consumo_financiado"]["value"] or 0))
    by_goal = D(str(body["financiado_objetivo"]["value"] or 0))
    by_portfolio = D(str(body["financiado_carteira"]["value"] or 0))
    assert by_goal + by_portfolio == total
    assert all("goal" in item for item in body["resgates_itens"])
