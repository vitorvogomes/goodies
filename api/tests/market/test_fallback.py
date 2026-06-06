"""Cadeia de fallback de preço (STORY-03-07): Redis → Postgres → null/stale.

Roda contra Postgres (goodies_test) e Redis reais. Tickers com prefixo MKT_ (limpos
pela fixture autouse). O caso de Redis indisponível usa um PriceCache numa porta morta.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from engines.market import service
from engines.market.cache import PriceCache

_NOW = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)


async def _insert_price(
    pool: Any, ticker: str, *, source: str, is_manual: bool, fetched_at: datetime
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual, fetched_at) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (ticker) DO UPDATE "
            "SET price_brl = EXCLUDED.price_brl, source = EXCLUDED.source, "
            "is_manual = EXCLUDED.is_manual, fetched_at = EXCLUDED.fetched_at",
            ticker,
            10.0,
            source,
            is_manual,
            fetched_at,
        )


@pytest.mark.asyncio
async def test_redis_hit_is_fresh(pool: Any) -> None:
    cache = PriceCache()
    await cache.set(
        service.price_cache_key("b3", "MKT_PETR4"),
        {
            "price_brl": 28.5,
            "price_usd": None,
            "source": "brapi",
            "fetched_at": "2026-06-06T11:00:00+00:00",
        },
        300,
    )
    try:
        async with pool.acquire() as conn:
            out = await service.get_price(
                conn, "MKT_PETR4", category="Ações Nacionais", now=_NOW
            )
        assert out["price_brl"] == 28.5
        assert out["stale"] is False
        assert out["source"] == "brapi"
    finally:
        await cache.delete(service.price_cache_key("b3", "MKT_PETR4"))


@pytest.mark.asyncio
async def test_postgres_hit_fresh_within_ttl(pool: Any) -> None:
    await _insert_price(
        pool, "MKT_BBAS3", source="brapi", is_manual=False, fetched_at=_NOW - timedelta(hours=1)
    )
    async with pool.acquire() as conn:
        out = await service.get_price(conn, "MKT_BBAS3", category="Ações Nacionais", now=_NOW)
    assert out["price_brl"] == 10.0
    assert out["stale"] is False  # 1h < TTL B3 (4h)


@pytest.mark.asyncio
async def test_postgres_hit_stale_past_ttl(pool: Any) -> None:
    await _insert_price(
        pool, "MKT_OLD", source="brapi", is_manual=False, fetched_at=_NOW - timedelta(hours=30)
    )
    async with pool.acquire() as conn:
        out = await service.get_price(conn, "MKT_OLD", category="Ações Nacionais", now=_NOW)
    assert out["stale"] is True  # 30h > TTL B3 (26h, cadência diária free-tier)


@pytest.mark.asyncio
async def test_manual_price_never_stale(pool: Any) -> None:
    await _insert_price(
        pool, "MKT_FLASH", source="manual", is_manual=True, fetched_at=_NOW - timedelta(days=30)
    )
    async with pool.acquire() as conn:
        out = await service.get_price(conn, "MKT_FLASH", category="Renda Fixa", now=_NOW)
    assert out["is_manual"] is True
    assert out["stale"] is False


@pytest.mark.asyncio
async def test_missing_price_returns_null_stale(pool: Any) -> None:
    async with pool.acquire() as conn:
        out = await service.get_price(conn, "MKT_NOPE", category="Ações Nacionais", now=_NOW)
    assert out["price_brl"] is None
    assert out["stale"] is True
    assert out["last_updated"] is None


@pytest.mark.asyncio
async def test_redis_down_falls_back_to_postgres(pool: Any, monkeypatch: Any) -> None:
    # cache apontado p/ porta morta → get falha soft (None) → cai p/ Postgres
    monkeypatch.setattr(service, "_cache", PriceCache(redis_url="redis://localhost:6399/0"))
    await _insert_price(
        pool, "MKT_DOWN", source="brapi", is_manual=False, fetched_at=_NOW - timedelta(hours=1)
    )
    async with pool.acquire() as conn:
        out = await service.get_price(conn, "MKT_DOWN", category="Ações Nacionais", now=_NOW)
    assert out["price_brl"] == 10.0  # Postgres respondeu, sem exceção
    assert out["stale"] is False


@pytest.mark.asyncio
async def test_cache_aside_write_populates_both(pool: Any) -> None:
    cache = PriceCache()
    async with pool.acquire() as conn:
        ok = await service.cache_aside_write(
            conn,
            "MKT_WRITE",
            cache_type="b3",
            price_brl=42.0,
            price_usd=None,
            source="brapi",
            ttl=300,
        )
        assert ok is True
        row = await conn.fetchrow(
            "SELECT price_brl, is_manual FROM asset_prices WHERE ticker = 'MKT_WRITE'"
        )
    assert float(row["price_brl"]) == 42.0
    assert row["is_manual"] is False
    hit = await cache.get(service.price_cache_key("b3", "MKT_WRITE"))
    assert hit is not None and hit["price_brl"] == 42.0
    await cache.delete(service.price_cache_key("b3", "MKT_WRITE"))


@pytest.mark.asyncio
async def test_cache_aside_write_respects_manual(pool: Any) -> None:
    # linha manual preexistente → worker não sobrescreve, nem popula Redis
    await _insert_price(
        pool, "MKT_MAN", source="manual", is_manual=True, fetched_at=_NOW
    )
    cache = PriceCache()
    await cache.delete(service.price_cache_key("b3", "MKT_MAN"))
    async with pool.acquire() as conn:
        ok = await service.cache_aside_write(
            conn, "MKT_MAN", cache_type="b3", price_brl=999.0,
            price_usd=None, source="brapi", ttl=300,
        )
        row = await conn.fetchrow(
            "SELECT price_brl, is_manual FROM asset_prices WHERE ticker = 'MKT_MAN'"
        )
    assert ok is False
    assert float(row["price_brl"]) == 10.0  # inalterado
    assert await cache.get(service.price_cache_key("b3", "MKT_MAN")) is None
