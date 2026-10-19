"""Story 10.2 — Ajustes › Preços manuais: só ativos sem fonte de mercado, com valor + data,
gravados com is_manual (nunca expira; o worker não sobrescreve); ativo com fonte de mercado é
recusado com "{Ativo} tem preço de mercado automático."."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt


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


@pytest.mark.asyncio
async def test_manual_price_in_dollars(api: Any, pool: Any, portfolio_user: dict) -> None:
    """O token cripto sem cotação se informa em dólar (como nas carteiras);
    o R$ sai da cotação do dólar (USDT/USDC) e é refeito quando ela muda — a data informada fica."""
    from engines.market import service

    headers = portfolio_user["headers"]
    async with pool.acquire() as conn:
        asset = await conn.fetchval(
            "INSERT INTO assets (key, name, class, price_ref, valuation) VALUES "
            "('manual:zzusd', 'ZZUSD', 'cripto', 'ZZUSD', 'manual') RETURNING id::text"
        )
        saved = await conn.fetchrow("SELECT * FROM asset_prices WHERE ticker = 'USDT'")
        await service.upsert_price(
            conn, "USDT", Decimal("5.40"), price_usd=1.0, source="coingecko", is_manual=False
        )
    try:
        r = await api.post(
            "/api/v1/market/prices/ZZUSD",
            json={"price_usd": "1.02", "as_of": "2026-10-01"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        listed = (await api.get("/api/v1/portfolio/manual-prices", headers=headers)).json()
        item = next(i for i in listed if i["ticker"] == "ZZUSD")
        assert Decimal(item["price_usd"]) == Decimal("1.02")
        assert Decimal(item["price_brl"]) == Decimal("5.508")
        assert item["currency"] == "USD"
        async with pool.acquire() as conn:
            await service.upsert_price(
                conn, "USDT", Decimal("5.50"), price_usd=1.0, source="coingecko", is_manual=False
            )
            assert await service.refresh_manual_usd(conn) >= 1
            row = await conn.fetchrow(
                "SELECT price_brl, is_manual, fetched_at::date AS d FROM asset_prices "
                "WHERE ticker = 'ZZUSD'"
            )
        assert row["price_brl"] == Decimal("5.61") and row["is_manual"]
        assert str(row["d"]) == "2026-10-01"
        # O histórico guarda cada dia na cotação do dia: o informado não muda; hoje é o novo.
        async with pool.acquire() as conn:
            history = {
                h["ref_date"]: h["price_brl"]
                for h in await conn.fetch(
                    "SELECT ref_date, price_brl FROM asset_price_history WHERE ticker = 'ZZUSD'"
                )
            }
        assert history[date(2026, 10, 1)] == Decimal("5.508")
        assert history[today_brt()] == Decimal("5.61")
        neither = await api.post("/api/v1/market/prices/ZZUSD", json={}, headers=headers)
        assert neither.status_code == 422
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = 'ZZUSD'")
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'ZZUSD'")
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", asset)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = 'USDT'")
            if saved is not None:
                await conn.execute(
                    "INSERT INTO asset_prices (ticker, price_brl, price_usd, source, is_manual, "
                    "fetched_at) VALUES ($1, $2, $3, $4, $5, $6)",
                    saved["ticker"],
                    saved["price_brl"],
                    saved["price_usd"],
                    saved["source"],
                    saved["is_manual"],
                    saved["fetched_at"],
                )
