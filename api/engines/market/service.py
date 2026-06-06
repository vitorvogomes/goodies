"""Market Engine — leitura de preço com fallback + cache-aside (STORY-03-07/09/10).

Cadeia de fallback (CLAUDE.md, ADR-004): **Redis → Postgres `asset_prices` → null/stale**.
Nunca levanta (sem HTTP 5xx por falha de fonte externa). É também o write path usado
pelos workers (`cache_aside_write`): grava em Postgres (via `portfolio.service.upsert_price`,
chokepoint §3.4 com precedência is_manual) e popula o Redis com a chave `price:{tipo}:{ticker}`.

`tipo` (b3/crypto/tesouro) deriva da categoria canônica do ativo (`constants` frozensets);
Renda Fixa & afins não têm fonte de mercado → `tipo=None` (preço sempre is_manual).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg

from config import settings
from engines.market.cache import PriceCache
from engines.portfolio import service as portfolio_service
from engines.portfolio.constants import (
    B3_CATEGORIES,
    CRYPTO_CATEGORIES,
    TREASURY_CATEGORIES,
)

_cache = PriceCache()

_TTL_BY_TYPE = {
    "b3": settings.ttl_b3,
    "crypto": settings.ttl_crypto,
    "tesouro": settings.ttl_tesouro,
}


def cache_type_for_category(category: str | None) -> str | None:
    """Categoria canônica -> tipo de cache/fetcher. None = sem fonte de mercado (is_manual)."""
    if category in B3_CATEGORIES:
        return "b3"
    if category in CRYPTO_CATEGORIES:
        return "crypto"
    if category in TREASURY_CATEGORIES:
        return "tesouro"
    return None


# source gravado em asset_prices -> tipo (p/ calcular staleness na leitura via Postgres).
_TYPE_BY_SOURCE = {"brapi": "b3", "b3": "b3", "coingecko": "crypto", "tesouro": "tesouro"}


def price_cache_key(cache_type: str, ticker: str) -> str:
    return f"price:{cache_type}:{ticker}"


async def invalidate_price_cache(ticker: str) -> None:
    """Remove o ticker do cache Redis após uma escrita manual (manual sempre vence).

    O preço manual é gravado no Postgres, mas a leitura (`get_price`) consulta o Redis
    primeiro pela `cache_type` da categoria — sem isto, um preço de mercado cacheado
    mascararia o override manual em `/market` por até o TTL. Apaga as 3 chaves candidatas
    (só uma existe); fail-soft.
    """
    for cache_type in ("b3", "crypto", "tesouro"):
        await _cache.delete(price_cache_key(cache_type, ticker))


def _is_stale(is_manual: bool, source: str, fetched_at: datetime, now: datetime) -> bool:
    """Manual nunca envelhece (autoritativo); de mercado, envelhece após o TTL do tipo."""
    if is_manual:
        return False
    ttl = _TTL_BY_TYPE.get(_TYPE_BY_SOURCE.get(source, ""), settings.ttl_b3)
    return (now - fetched_at).total_seconds() > ttl


def _missing(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "price_brl": None,
        "price_usd": None,
        "source": None,
        "is_manual": False,
        "stale": True,
        "last_updated": None,
    }


async def get_price(
    conn: asyncpg.Connection,
    ticker: str,
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Preço corrente do ticker pela cadeia Redis → Postgres → null/stale. Nunca levanta."""
    now = now or datetime.now(tz=UTC)
    cache_type = cache_type_for_category(category)
    if cache_type is not None:
        hit = await _cache.get(price_cache_key(cache_type, ticker))
        if hit is not None:  # presente no Redis ⇒ dentro do TTL ⇒ fresco
            return {
                "ticker": ticker,
                "price_brl": hit.get("price_brl"),
                "price_usd": hit.get("price_usd"),
                "source": hit.get("source"),
                "is_manual": False,
                "stale": False,
                "last_updated": hit.get("fetched_at"),
            }

    row = await conn.fetchrow(
        "SELECT price_brl, price_usd, source, is_manual, fetched_at "
        "FROM asset_prices WHERE ticker = $1",
        ticker,
    )
    if row is None:
        return _missing(ticker)
    fetched_at: datetime = row["fetched_at"]
    return {
        "ticker": ticker,
        "price_brl": float(row["price_brl"]),
        "price_usd": float(row["price_usd"]) if row["price_usd"] is not None else None,
        "source": row["source"],
        "is_manual": row["is_manual"],
        "stale": _is_stale(row["is_manual"], row["source"], fetched_at, now),
        "last_updated": fetched_at.isoformat(),
    }


async def list_user_prices(
    conn: asyncpg.Connection, user_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Preço corrente de todos os tickers que o usuário detém (via fallback)."""
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol, asset_category FROM asset_operations "
        "WHERE user_id = $1 ORDER BY asset_symbol",
        user_id,
    )
    return [
        await get_price(conn, r["asset_symbol"], category=r["asset_category"], now=now)
        for r in rows
    ]


async def cache_aside_write(
    conn: asyncpg.Connection,
    ticker: str,
    *,
    cache_type: str,
    price_brl: float,
    price_usd: float | None,
    source: str,
    ttl: int,
) -> bool:
    """Grava um preço de mercado: Postgres (chokepoint) + Redis. Usado pelos workers.

    Respeita a precedência is_manual (a escrita em Postgres é ignorada sobre linha
    manual); nesse caso NÃO popula o Redis (não contradiz o preço manual). Retorna
    True se gravou, False se foi ignorado.
    """
    written = await portfolio_service.upsert_price(
        conn, ticker, price_brl, price_usd=price_usd, source=source, is_manual=False
    )
    if not written:
        return False
    await _cache.set(
        price_cache_key(cache_type, ticker),
        {
            "price_brl": price_brl,
            "price_usd": price_usd,
            "source": source,
            "fetched_at": written["fetched_at"].isoformat(),
        },
        ttl,
    )
    return True
