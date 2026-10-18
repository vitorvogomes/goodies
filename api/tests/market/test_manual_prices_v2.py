"""Story 10.2 — Ajustes › Preços manuais: só ativos sem fonte de mercado, com valor + data,
gravados com is_manual (nunca expira; o worker não sobrescreve); ativo com fonte de mercado é
recusado com "{Ativo} tem preço de mercado automático."."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_market_asset_is_refused(api: Any, pool: Any, portfolio_user: dict) -> None:
    uid, headers = portfolio_user["user_id"], portfolio_user["headers"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'MKT_B3X', 'Ações Nacionais', 'compra', 10, 5, '2026-01-01')",
            uid,
        )
    r = await api.post("/api/v1/market/prices/MKT_B3X", json={"price_brl": 40.0}, headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == {
        "error": "preco_de_mercado",
        "message": "MKT_B3X tem preço de mercado automático.",
    }


@pytest.mark.asyncio
async def test_manual_with_date_and_listing(api: Any, pool: Any, portfolio_user: dict) -> None:
    headers = portfolio_user["headers"]
    async with pool.acquire() as conn:
        asset = await conn.fetchval(
            "INSERT INTO assets (key, name, class, price_ref, valuation) VALUES "
            "('manual:zzneo', 'ZZNEO', 'cripto', 'ZZNEO', 'manual') RETURNING id::text"
        )
    try:
        r = await api.post(
            "/api/v1/market/prices/ZZNEO",
            json={"price_brl": "0.0042", "as_of": "2026-10-01"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        listed = (await api.get("/api/v1/portfolio/manual-prices", headers=headers)).json()
        item = next(i for i in listed if i["ticker"] == "ZZNEO")
        # preço unitário abaixo de um centavo, sem arredondar e sem float (texto decimal)
        assert Decimal(item["price_brl"]) == Decimal("0.0042")
        assert (item["as_of"], item["is_manual"]) == ("2026-10-01", True)
        bad = await api.post(
            "/api/v1/market/prices/ZZNEO", json={"price_brl": "-1"}, headers=headers
        )
        assert bad.status_code == 422
        assert all(i["ticker"] != "MKT_B3X" for i in listed)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = 'ZZNEO'")
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'ZZNEO'")
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", asset)
