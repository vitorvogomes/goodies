"""P28 — saldo informado da renda fixa pelo CDI: o saldo que o app do banco mostra (ou cotas ×
valor da cota, no fundo da Reserva) numa data; dali em diante rende o %CDI do ativo."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from engines.portfolio import rf_anchors

D = Decimal


@pytest.fixture
async def asset(pool):
    from engines.common.owner import get_owner_id

    symbol = f"RF-{uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        asset_id = await conn.fetchval(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'Nubank', $2, 'Renda Fixa', "
            "'aporte', 1000, 1, '2025-03-03') RETURNING asset_id",
            owner,
            symbol,
        )
        await conn.execute(
            "UPDATE assets SET valuation = 'cdi', pct_cdi = 100 WHERE id = $1", asset_id
        )
    yield symbol
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM rf_balance_anchors WHERE asset_id = $1", asset_id)
        await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", symbol)
        await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", symbol)
        await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", symbol)
        await conn.execute("DELETE FROM asset_aliases WHERE asset_id = $1", asset_id)
        await conn.execute("DELETE FROM assets WHERE id = $1", asset_id)


@pytest.mark.asyncio
async def test_save_anchor_by_quotas_and_pct(pool, asset) -> None:
    from engines.common.owner import get_owner_id
    from engines.portfolio.valuation import valuation_as_of

    async with pool.acquire() as conn:
        row = await rf_anchors.save_anchor(
            conn,
            asset,
            rf_anchors.AnchorIn(
                as_of=date(2025, 3, 5), quotas=D("5970.88989"), quota_value=D("1.79494")
            ),
        )
        assert row.value == (D("5970.88989") * D("1.79494")).quantize(D("0.01"))
        listed = {r.ticker: r for r in await rf_anchors.list_rf(conn)}
        assert listed[asset].anchor_date == date(2025, 3, 5)
        assert listed[asset].quotas == D("5970.88989")
        owner = await get_owner_id(conn)
        val = await valuation_as_of(conn, owner, date(2025, 3, 5))
        assert val.by_asset[asset] == row.value

        await rf_anchors.save_anchor(
            conn, asset, rf_anchors.AnchorIn(as_of=date(2025, 3, 5), value=D("900"), pct_cdi=D(95))
        )
        listed = {r.ticker: r for r in await rf_anchors.list_rf(conn)}
        assert listed[asset].value == D("900.00") and listed[asset].quotas is None
        assert listed[asset].pct_cdi == D(95)


@pytest.mark.asyncio
async def test_rejects_future_and_unknown(pool, asset) -> None:
    async with pool.acquire() as conn:
        with pytest.raises(rf_anchors.FutureAnchorError):
            await rf_anchors.save_anchor(
                conn, asset, rf_anchors.AnchorIn(as_of=date(2099, 1, 1), value=D(1))
            )
        with pytest.raises(LookupError):
            await rf_anchors.save_anchor(
                conn, "nao-existe", rf_anchors.AnchorIn(as_of=date(2025, 1, 1), value=D(1))
            )


@pytest.mark.asyncio
async def test_routes(api, auth_headers, asset) -> None:
    listed = (await api.get("/api/v1/portfolio/renda-fixa", headers=auth_headers)).json()
    assert any(r["ticker"] == asset for r in listed)
    r = await api.put(
        f"/api/v1/portfolio/renda-fixa/{asset}",
        json={"as_of": "2025-03-05", "value": "1001.50"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert D(str(r.json()["value"])) == D("1001.50")
    bad = await api.put(
        f"/api/v1/portfolio/renda-fixa/{asset}",
        json={"as_of": "2025-03-05"},
        headers=auth_headers,
    )
    assert bad.status_code == 422
