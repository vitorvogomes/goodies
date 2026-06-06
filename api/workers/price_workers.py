"""Workers de atualização de preço (STORY-03-05/06). Corpos desacoplados do scheduler.

Cada run: descobre os tickers da carteira na(s) categoria(s) alvo, busca via fetcher
(fail-soft) e grava por `market.service.cache_aside_write` (Postgres chokepoint §3.4 +
Redis). Idempotentes (ON CONFLICT + precedência is_manual + cache TTL). Rodáveis fora
do cron (testes/integração) recebendo o pool e, opcionalmente, fetchers injetados.
"""
from __future__ import annotations

from collections.abc import Iterable

import asyncpg

from config import settings
from engines.market import service
from engines.market.fetchers.base import PriceFetcher
from engines.market.fetchers.brapi import BrapiFetcher
from engines.market.fetchers.coingecko import CoinGeckoFetcher
from engines.market.fetchers.treasury import TreasuryFetcher
from engines.portfolio.constants import (
    B3_CATEGORIES,
    CRYPTO_CATEGORIES,
    TREASURY_CATEGORIES,
)


async def _symbols_in(conn: asyncpg.Connection, categories: Iterable[str]) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol FROM asset_operations "
        "WHERE asset_category = ANY($1::text[])",
        [str(c) for c in categories],
    )
    return [r["asset_symbol"] for r in rows]


async def _run_for(
    conn: asyncpg.Connection,
    categories: Iterable[str],
    fetcher: PriceFetcher,
    cache_type: str,
    ttl: int,
) -> dict[str, int]:
    symbols = await _symbols_in(conn, categories)
    if not symbols:
        return {"symbols": 0, "fetched": 0, "updated": 0, "skipped": 0, "failed": 0}
    quotes = await fetcher.fetch(symbols)
    updated = skipped = 0
    for sym, q in quotes.items():
        ok = await service.cache_aside_write(
            conn,
            sym,
            cache_type=cache_type,
            price_brl=q.price_brl,
            price_usd=q.price_usd,
            source=q.source,
            ttl=ttl,
        )
        updated += 1 if ok else 0
        skipped += 0 if ok else 1
    return {
        "symbols": len(symbols),
        "fetched": len(quotes),
        "updated": updated,
        "skipped": skipped,  # ignorados pela precedência is_manual
        "failed": len(symbols) - len(quotes),  # sem cotação na fonte
    }


async def run_price_b3(
    pool: asyncpg.Pool,
    *,
    brapi: PriceFetcher | None = None,
    treasury: PriceFetcher | None = None,
) -> dict[str, dict[str, int]]:
    """Atualiza B3 (ações/ETFs/FIIs via BRAPI) + Tesouro (mesma cadência de dia útil)."""
    brapi = brapi or BrapiFetcher()
    treasury = treasury or TreasuryFetcher()
    async with pool.acquire() as conn:
        b3 = await _run_for(conn, B3_CATEGORIES, brapi, "b3", settings.ttl_b3)
        td = await _run_for(conn, TREASURY_CATEGORIES, treasury, "tesouro", settings.ttl_tesouro)
    return {"b3": b3, "tesouro": td}


async def run_price_crypto(
    pool: asyncpg.Pool, *, fetcher: PriceFetcher | None = None
) -> dict[str, int]:
    """Atualiza cripto via CoinGecko (cron a cada 2h; NUNCA on-demand — CLAUDE.md)."""
    fetcher = fetcher or CoinGeckoFetcher()
    async with pool.acquire() as conn:
        return await _run_for(conn, CRYPTO_CATEGORIES, fetcher, "crypto", settings.ttl_crypto)
