"""Market Engine — leitura de preço com fallback + cache-aside (STORY-03-07/09/10).

Cadeia de fallback (CLAUDE.md, ADR-004): **Redis → Postgres `asset_prices` → null/stale**.
Nunca levanta (sem HTTP 5xx por falha de fonte externa). É também o write path usado
pelos workers (`cache_aside_write`): grava em Postgres (via `portfolio.service.upsert_price`,
chokepoint §3.4 com precedência is_manual) e popula o Redis com a chave `price:{tipo}:{ticker}`.

`tipo` (b3/crypto/tesouro) deriva da categoria canônica do ativo (`constants` frozensets);
Renda Fixa & afins não têm fonte de mercado → `tipo=None` (preço sempre is_manual).
"""
from __future__ import annotations

from collections.abc import Sequence
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


def _from_cache_hit(ticker: str, hit: dict[str, Any]) -> dict[str, Any]:
    """Preço a partir de um hit no Redis: presente ⇒ dentro do TTL ⇒ fresco."""
    return {
        "ticker": ticker,
        "price_brl": hit.get("price_brl"),
        "price_usd": hit.get("price_usd"),
        "source": hit.get("source"),
        "is_manual": False,
        "stale": False,
        "last_updated": hit.get("fetched_at"),
    }


def _from_pg_row(ticker: str, row: Any, now: datetime) -> dict[str, Any]:
    """Preço a partir de uma linha de asset_prices (staleness por TTL/is_manual)."""
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
        if hit is not None:
            return _from_cache_hit(ticker, hit)

    row = await conn.fetchrow(
        "SELECT price_brl, price_usd, source, is_manual, fetched_at "
        "FROM asset_prices WHERE ticker = $1",
        ticker,
    )
    if row is None:
        return _missing(ticker)
    return _from_pg_row(ticker, row, now)


async def list_user_prices(
    conn: asyncpg.Connection, user_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Preço corrente de todos os tickers do usuário (mesma cadeia de fallback do
    `get_price`, mas em LOTE: 1 SELECT `ticker = ANY($1)` + 1 Redis MGET, em vez de
    N idas por ticker). A carteira cresce no m4 (cripto/wallets) → evita o N+1 (§debito m3 #2).
    """
    now = now or datetime.now(tz=UTC)
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol, asset_category FROM asset_operations "
        "WHERE user_id = $1 ORDER BY asset_symbol",
        user_id,
    )
    if not rows:
        return []
    tickers = [r["asset_symbol"] for r in rows]
    category_of = {r["asset_symbol"]: r["asset_category"] for r in rows}

    # 1 SELECT em lote (substitui o fetchrow por ticker do get_price)
    pg = {
        r["ticker"]: r
        for r in await conn.fetch(
            "SELECT ticker, price_brl, price_usd, source, is_manual, fetched_at "
            "FROM asset_prices WHERE ticker = ANY($1)",
            tickers,
        )
    }
    # 1 Redis MGET só nos tickers com fonte de mercado (cache_type != None)
    typed = [
        (t, ct) for t in tickers if (ct := cache_type_for_category(category_of[t])) is not None
    ]
    hits = await _cache.mget([price_cache_key(ct, t) for t, ct in typed])
    cached = {t: v for (t, _ct), v in zip(typed, hits, strict=True) if v is not None}

    out: list[dict[str, Any]] = []
    for ticker in tickers:
        hit = cached.get(ticker)
        if hit is not None:
            out.append(_from_cache_hit(ticker, hit))
        elif (row := pg.get(ticker)) is not None:
            out.append(_from_pg_row(ticker, row, now))
        else:
            out.append(_missing(ticker))
    return out


async def prices_for_tickers(
    conn: asyncpg.Connection,
    tickers: Sequence[str],
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> dict[str, tuple[float | None, float | None]]:
    """Preço (BRL, USD) por ticker em LOTE pela cadeia Redis→Postgres (cache-aside do m3).

    Valoração de wallet/DeFi: todos cripto → `category='Cripto'` usa o cache cripto (em vez
    de bater só no Postgres). Reusa as chaves/builders do m3; sem N+1 e sem SELECT de preço
    duplicado fora desta engine. Ticker ausente NÃO entra no dict (call site faz
    `.get(sym, (None, None))`).
    """
    keys = list(dict.fromkeys(tickers))  # dedup preservando ordem
    if not keys:
        return {}
    now = now or datetime.now(tz=UTC)
    cache_type = cache_type_for_category(category)

    pg = {
        r["ticker"]: r
        for r in await conn.fetch(
            "SELECT ticker, price_brl, price_usd FROM asset_prices WHERE ticker = ANY($1)",
            keys,
        )
    }
    cached: dict[str, Any] = {}
    if cache_type is not None:
        hits = await _cache.mget([price_cache_key(cache_type, t) for t in keys])
        cached = {t: v for t, v in zip(keys, hits, strict=True) if v is not None}

    out: dict[str, tuple[float | None, float | None]] = {}
    for t in keys:
        hit = cached.get(t)
        if hit is not None:
            out[t] = (hit.get("price_brl"), hit.get("price_usd"))
        elif (row := pg.get(t)) is not None:
            out[t] = (
                float(row["price_brl"]) if row["price_brl"] is not None else None,
                float(row["price_usd"]) if row["price_usd"] is not None else None,
            )
    return out


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
