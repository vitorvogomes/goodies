#!/usr/bin/env python3
"""Seed manual asset prices from docs/Utils/posicao.json. Idempotent (upsert).

Em m2 nao ha Market Engine: a valoracao de posicoes usa o ultimo preco manual.
Este script popula asset_prices com os valores disponiveis no snapshot da carteira:
- RF privada / Tesouro / DeFi / USDT: tem `valor_atual_base` (valor total da posicao).
  Como modelamos esses ativos com quantidade=1, price_brl = valor_atual_base.
- Acoes / ETF / FII / cripto: o snapshot so tem custo (preco_medio), nao o preco
  atual de mercado -> nao sao seedados aqui (ficam stale ate input manual ou m3).

Uso: python scripts/seed_asset_prices.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.portfolio.service import upsert_price

_POSICAO = Path(__file__).parent.parent / "docs" / "Utils" / "posicao.json"


def _manual_prices() -> list[tuple[str, float]]:
    """Extrai (ticker, valor_atual_base) dos ativos que tem valor atual no snapshot."""
    data = json.loads(_POSICAO.read_text(encoding="utf-8"))
    out: list[tuple[str, float]] = []
    for asset in data["ativos"]:
        base = asset.get("valor_atual_base")
        if base is not None:
            out.append((str(asset["ticker"]), float(base)))
    return out


async def main() -> None:
    dry_run = "--dry-run" in sys.argv

    print("=" * 70)
    print("ASSET PRICES SEEDER (manual — posicao.json)")
    print("=" * 70)

    prices = _manual_prices()
    print(f"\nManual prices found in snapshot: {len(prices)}")
    for ticker, price in prices:
        print(f"  - {ticker:24s} R$ {price:>12,.2f}")

    if dry_run:
        print("\n(dry-run mode — no changes made)")
        return

    try:
        await init_pool(settings.database_url)
        pool = get_pool()
        async with pool.acquire() as conn:
            for ticker, price in prices:
                await upsert_price(conn, ticker, price, source="manual")
        print(f"\n[ok] Seeded {len(prices)} manual prices")
    finally:
        await close_pool()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
