"""v2.2 — DeFi pelo saldo em US$: o saldo que o protocolo mostra numa data e, se informado, o APY;
o valor rende por dia até o próximo saldo. O preço do token (US$ = valor ÷ quantidade, R$ pela
cotação do dólar) é gravado como manual (`defi_anchor`), então Posições, histórico e sleeve seguem
iguais. O token com saldo informado sai de Preços manuais."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest

from engines.common.dates import today_brt
from engines.wallet.defi_anchors import Anchor, price_on

D = Decimal


def test_value_without_apy_stays_flat() -> None:
    a = [Anchor(date(2026, 10, 1), D("100.00"), None)]
    assert price_on(a, date(2026, 12, 31)) == D("100.00")


def test_value_compounds_daily_by_apy_from_latest_anchor() -> None:
    a = [
        Anchor(date(2026, 1, 1), D("50.00"), D("20")),
        Anchor(date(2026, 7, 1), D("100.00"), D("10")),
    ]
    assert price_on(a, date(2026, 7, 1)) == D("100.00")
    assert price_on(a, date(2027, 7, 1)) == D("110.00")  # 365 dias a 10% a.a.
    assert price_on(a, date(2026, 3, 1)) is not None  # antes do 2º, vale o 1º
    assert price_on(a, date(2025, 12, 31)) is None  # antes do 1º saldo: sem valor


def test_price_per_token_follows_the_anchor_so_deposits_add_value() -> None:
    """Review v2.2: o preço por token (saldo ÷ quantidade da data) rende o APY; um depósito depois
    do saldo entra por esse preço em vez de diluir o saldo informado."""
    a = [Anchor(date(2026, 1, 1), D("500.00"), D("10"), D(100))]
    assert price_on(a, date(2026, 1, 1)) == D("5.00000000")
    assert price_on(a, date(2027, 1, 1)) == D("5.50000000")
    assert price_on(a, date(2025, 12, 31)) is None


@pytest.mark.asyncio
async def test_saving_balance_reprices_token_and_leaves_manual_prices(
    api: httpx.AsyncClient, wallet_user: dict, pool: Any
) -> None:
    sym = f"T{uuid.uuid4().hex[:6].upper()}"
    h = wallet_user["headers"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, price_usd, source, is_manual) "
            "VALUES ('USDT', 5.50, 1, 'coingecko', false) ON CONFLICT (ticker) DO UPDATE SET "
            "price_brl = 5.50, price_usd = 1, source = 'coingecko', is_manual = false"
        )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, price_usd, source, is_manual) "
            "VALUES ($1, 8, 1.45, 'manual_usd', true)",
            sym,
        )
        # o token tinha preço manual (como o PT sUSDai): aparece em Preços manuais até ter saldo
        await conn.execute(
            "INSERT INTO assets (key, class, name, price_ref, valuation) "
            "VALUES ($1, 'cripto', $2, $2, 'manual')",
            f"crypto:{sym}",
            sym,
        )
    before = (await api.get("/api/v1/portfolio/manual-prices", headers=h)).json()
    assert sym in [c["ticker"] for c in before]
    try:
        pid = (
            await api.post(
                "/api/v1/defi/positions", json={"asset_symbol": sym, "balance": 40}, headers=h
            )
        ).json()["id"]
        day = today_brt() - timedelta(days=10)
        r = await api.put(
            f"/api/v1/defi/positions/{pid}/balance",
            json={"as_of": day.isoformat(), "value_usd": "60.00", "apy": "12"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["anchor"]["value_usd"] == 60.0 and body["anchor"]["apy"] == 12.0
        assert 60.0 < body["value_usd"] < 60.5  # 10 dias a 12% a.a.
        assert body["value_brl"] == pytest.approx(body["value_usd"] * 5.5, abs=0.02)
        async with pool.acquire() as conn:
            price = await conn.fetchrow(
                "SELECT price_usd, source, is_manual FROM asset_prices WHERE ticker = $1", sym
            )
            assert price["source"] == "defi_anchor" and price["is_manual"]
            assert float(price["price_usd"]) == pytest.approx(body["value_usd"] / 40, rel=1e-6)
        manual = (await api.get("/api/v1/wallets/manual", headers=h)).json()
        row = next(i for i in manual if i["id"] == pid)
        assert row["anchor"]["apy"] == 12.0
        assert row["value_usd"] == pytest.approx(body["value_usd"], abs=0.01)
        listed = (await api.get("/api/v1/defi/positions", headers=h)).json()
        mine = next(p for p in listed if p["id"] == pid)
        assert mine["anchor"]["value_usd"] == 60.0
        cands = (await api.get("/api/v1/portfolio/manual-prices", headers=h)).json()
        assert sym not in [c["ticker"] for c in cands]  # o saldo é a fonte
        future = await api.put(
            f"/api/v1/defi/positions/{pid}/balance",
            json={"as_of": (today_brt() + timedelta(days=1)).isoformat(), "value_usd": "1"},
            headers=h,
        )
        assert future.status_code == 422
        # depósito depois do saldo: o preço por token fica, o valor sobe com a quantidade
        await api.put(f"/api/v1/defi/positions/{pid}", json={"balance": 80}, headers=h)
        manual2 = (await api.get("/api/v1/wallets/manual", headers=h)).json()
        doubled = next(i for i in manual2 if i["id"] == pid)["value_usd"]
        assert doubled == pytest.approx(2 * body["value_usd"], abs=0.05)
        # apagar a posição libera o preço: volta a manual em dólar (segue a cotação)
        assert (await api.delete(f"/api/v1/defi/positions/{pid}", headers=h)).status_code == 204
        async with pool.acquire() as conn:
            assert (
                await conn.fetchval("SELECT source FROM asset_prices WHERE ticker = $1", sym)
                == "manual_usd"
            )
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", sym)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", sym)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"crypto:{sym}")


@pytest.mark.asyncio
async def test_balance_refused_for_market_priced_token(
    api: httpx.AsyncClient, wallet_user: dict
) -> None:
    """Review v2.2: SOL/USDC têm cotação — o saldo em US$ gravaria um preço manual e congelaria o
    preço de mercado de todo o SOL da carteira."""
    h = wallet_user["headers"]
    pid = (
        await api.post(
            "/api/v1/defi/positions", json={"asset_symbol": "SOL", "balance": 2}, headers=h
        )
    ).json()["id"]
    r = await api.put(
        f"/api/v1/defi/positions/{pid}/balance",
        json={"as_of": today_brt().isoformat(), "value_usd": "300"},
        headers=h,
    )
    assert r.status_code == 422 and "cotação de mercado" in r.text
