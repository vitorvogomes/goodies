"""Histórico diário de preço cripto pelo CoinGecko (P23): os últimos 365 dias (o limite da API
gratuita) de cada ativo cripto mapeado em `settings.coingecko_ids`, para o bloco cripto ter preço
nas datas passadas (a quantidade por data vem de `wallet_position_history`, desde jun/2026). Grava
só os dias que faltam em `asset_price_history` (nunca sobrescreve); com backup antes. Desde a v2.2
o job mensal `price_history` faz o mesmo (com B3 e Tesouro); este script fica para a carga avulsa.

Uso (a partir de api/):
    uv run python -m scripts.ops.backfill_precos_cripto
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx

from config import settings
from engines.market.history_backfill import crypto_history, parse_market_chart, write_missing
from workers.backup import make_pre_migration_backup

__all__ = ["backfill", "parse_market_chart"]


async def backfill(
    conn: asyncpg.Connection,
    ids: dict[str, str | None],
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Ticker → dias gravados. Ticker sem id do CoinGecko fica de fora; falha de um não para os
    outros (nunca levanta por API externa). A busca e a gravação são as do job `price_history`
    (`engines.market.history_backfill`, v2.2)."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        found = await crypto_history(ids, http, days=days, pause=2.5 if own else 0)
    finally:
        if own:
            await http.aclose()
    return {t: await write_missing(conn, t, points, "coingecko") for t, points in found.items()}


async def _held_tickers(conn: asyncpg.Connection) -> dict[str, str | None]:
    """Os símbolos das carteiras e da DeFi com o id do CoinGecko (pelo nome em maiúsculas)."""
    symbols = {
        r["asset_symbol"]
        for r in await conn.fetch(
            "SELECT asset_symbol FROM wallet_positions "
            "UNION SELECT asset_symbol FROM defi_positions"
        )
    }
    return {s: settings.coingecko_ids.get(s.upper()) for s in sorted(symbols)}


async def _main() -> None:
    await make_pre_migration_backup(settings.database_url, "pre-backfill-cripto")
    conn = await asyncpg.connect(settings.database_url)
    try:
        stats: dict[str, Any] = await backfill(conn, await _held_tickers(conn))
    finally:
        await conn.close()
    for ticker, n in stats.items():
        print(f"{ticker}: {n} dias gravados")


if __name__ == "__main__":
    asyncio.run(_main())
