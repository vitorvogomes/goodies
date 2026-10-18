"""Histórico diário de preço cripto pelo CoinGecko (P23): os últimos 365 dias (o limite da API
gratuita) de cada ativo cripto mapeado em `settings.coingecko_ids`, para o bloco cripto ter preço
nas datas passadas (a quantidade por data vem de `wallet_position_history`, desde jun/2026). Grava
só os dias que faltam em `asset_price_history` (nunca sobrescreve); com backup antes.

Uso (a partir de api/):
    uv run python -m scripts.ops.backfill_precos_cripto
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import asyncpg
import httpx

from config import settings
from workers.backup import make_pre_migration_backup

_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"


def parse_market_chart(payload: dict[str, Any]) -> list[tuple[date, float]]:
    """`prices: [[ms, preço], ...]` → um preço por dia (UTC; o último do dia)."""
    by_day: dict[date, float] = {}
    for ms, price in payload.get("prices", []):
        by_day[datetime.fromtimestamp(ms / 1000, tz=UTC).date()] = float(price)
    return sorted(by_day.items())


async def backfill(
    conn: asyncpg.Connection,
    ids: dict[str, str | None],
    *,
    days: int = 365,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Ticker → dias gravados. Ticker sem id do CoinGecko fica de fora; falha de um não para os
    outros (nunca levanta por API externa)."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    headers = (
        {"x-cg-demo-api-key": settings.coingecko_api_key} if settings.coingecko_api_key else {}
    )
    out: dict[str, int] = {}
    try:
        for ticker, coin in ids.items():
            if not coin:
                continue
            try:
                resp = await http.get(
                    _URL.format(id=coin),
                    params={"vs_currency": "brl", "days": days, "interval": "daily"},
                    headers=headers,
                )
                resp.raise_for_status()
                points = parse_market_chart(resp.json())
            except (httpx.HTTPError, ValueError):
                continue
            written = 0
            for day, price in points:
                status = await conn.execute(
                    "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, "
                    "is_manual) VALUES ($1, $2, $3, 'coingecko', false) "
                    "ON CONFLICT (ticker, ref_date) DO NOTHING",
                    ticker,
                    day,
                    price,
                )
                written += status.endswith(" 1")
            out[ticker] = written
            await asyncio.sleep(2.5 if own else 0)  # API gratuita: ~30 chamadas/min
    finally:
        if own:
            await http.aclose()
    return out


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
        stats = await backfill(conn, await _held_tickers(conn))
    finally:
        await conn.close()
    for ticker, n in stats.items():
        print(f"{ticker}: {n} dias gravados")


if __name__ == "__main__":
    asyncio.run(_main())
