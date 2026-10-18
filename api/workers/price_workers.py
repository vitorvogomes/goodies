"""Workers de atualização de preço (STORY-03-05/06). Corpos desacoplados do scheduler.

Cada run: descobre os tickers da carteira na(s) categoria(s) alvo, busca via fetcher
(fail-soft) e grava por `market.service.cache_aside_write` (Postgres chokepoint §3.4 +
Redis). Idempotentes (ON CONFLICT + precedência is_manual + cache TTL). Rodáveis fora
do cron (testes/integração) recebendo o pool e, opcionalmente, fetchers injetados.
"""
from __future__ import annotations

from collections.abc import Iterable

import asyncpg
import structlog

from config import settings
from engines.common.assets import (
    B3_CATEGORIES,
    CRYPTO_CATEGORIES,
    TREASURY_CATEGORIES,
)
from engines.market import service
from engines.market.fetchers.base import PriceFetcher
from engines.market.fetchers.brapi import BrapiFetcher
from engines.market.fetchers.coingecko import CoinGeckoFetcher
from engines.market.fetchers.treasury import TreasuryFetcher

logger = structlog.get_logger()


async def _symbols_in(conn: asyncpg.Connection, categories: Iterable[str]) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol FROM asset_operations "
        "WHERE asset_category = ANY($1::text[])",
        [str(c) for c in categories],
    )
    return [r["asset_symbol"] for r in rows]


async def _distinct_symbols(conn: asyncpg.Connection, sql: str, label: str) -> list[str]:
    """`SELECT DISTINCT asset_symbol` fail-soft (m4): tabela ausente / SELECT falha → [].

    Não derruba o cron de preço cripto (que existia antes do m4). Símbolo sem alias no
    mapa do fetcher (ex.: YT-xSOL-2609) é ignorado mais adiante.
    """
    try:
        rows = await conn.fetch(sql)
    except Exception as exc:
        logger.warning("distinct_symbols_failed", label=label, error=str(exc))
        return []
    return [r["asset_symbol"] for r in rows]


async def _run_for(
    conn: asyncpg.Connection,
    categories: Iterable[str],
    fetcher: PriceFetcher,
    cache_type: str,
    ttl: int,
    *,
    extra_symbols: Iterable[str] = (),
) -> dict[str, int]:
    # une os tickers das ops (core) com os escaneados (m4); o fetcher ignora os fora do mapa.
    core = await _symbols_in(conn, categories)
    symbols = sorted(set(core) | set(extra_symbols))
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
        # só os tickers "core" (das categorias de mercado) sem cotação são falha de fonte;
        # extras de wallet sem mapeamento no fetcher NÃO contam (não há fonte p/ eles) —
        # EXCETO no apagão total: símbolos pedidos e zero cotações é falha de fonte mesmo
        # com core vazio (cripto não vive em asset_operations; sem isso o worker cripto
        # reportava failed=0 com o CoinGecko 100% fora).
        "failed": _blackout_count(fetcher, core, symbols)
        if not quotes
        else len(set(core) - set(quotes)),
    }


def _blackout_count(fetcher: PriceFetcher, core: Iterable[str], symbols: Iterable[str]) -> int:
    """Zero cotações: conta como falha o core + os extras que o fetcher SABE cotar.

    Extras sem mapeamento (ex.: YT-XSOL) não têm fonte — se só eles foram pedidos, o
    fetcher nem consulta a API e isso não é apagão. Fetcher sem `supports` (sem mapa)
    trata todo símbolo como cotável (comportamento anterior).
    """
    supports = getattr(fetcher, "supports", None)
    if supports is None:
        return len(set(symbols))
    return len(set(core) | {s for s in symbols if supports(s)})


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
    """Atualiza cripto via CoinGecko (cron a cada 2h; NUNCA on-demand — CLAUDE.md).

    Inclui os símbolos escaneados em wallet_positions e os das posições DeFi (m4), além
    das ops, p/ que uma cripto só-de-wallet ou só-DeFi também receba preço/valor.
    """
    fetcher = fetcher or CoinGeckoFetcher()
    async with pool.acquire() as conn:
        wallet = await _distinct_symbols(
            conn, "SELECT DISTINCT asset_symbol FROM wallet_positions", "wallet"
        )
        defi = await _distinct_symbols(
            conn, "SELECT DISTINCT asset_symbol FROM defi_positions WHERE is_active", "defi"
        )
        return await _run_for(
            conn, CRYPTO_CATEGORIES, fetcher, "crypto", settings.ttl_crypto,
            extra_symbols=set(wallet) | set(defi),
        )
