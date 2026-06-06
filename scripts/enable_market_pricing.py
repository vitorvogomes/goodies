#!/usr/bin/env python3
"""Destrava o pricing automático: marca is_manual=false nos preços de ativos com fonte
de mercado (B3 via BRAPI + Tesouro via Tesouro Transparente), para o worker do Market
Engine poder refrescá-los.

Os preços B3/Tesouro foram semeados com is_manual=true por uma versão antiga do import_b3;
o chokepoint upsert_price (precedência §3.4) impede o worker de sobrescrever linha manual.
Este script faz o flip one-time. Só os preços genuinamente manuais (Flash-Debênture +
caixinhas/CDB Nubank, sem fonte de mercado) permanecem is_manual=true.

Uso (banco curado local):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python ../scripts/enable_market_pricing.py            # dry-run
    DATABASE_URL=... uv run python ../scripts/enable_market_pricing.py --commit
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

import asyncpg

from config import settings

# Categorias com fonte de mercado: Ações/ETFs/FIIs (BRAPI) + Aposentadoria (Tesouro
# Transparente CSV). Renda Fixa (caixinhas/Flash/CDB) e Cripto (m4) ficam de fora.
_CATEGORIES = ["Ações Nacionais", "ETFs", "FIIs", "Aposentadoria"]
_SELECT_TICKERS = (
    "SELECT DISTINCT asset_symbol FROM asset_operations WHERE asset_category = ANY($1::text[])"
)


async def main() -> None:
    commit = "--commit" in sys.argv
    conn = await asyncpg.connect(settings.database_url)
    try:
        rows = await conn.fetch(
            f"SELECT ticker, source FROM asset_prices "
            f"WHERE is_manual = true AND ticker IN ({_SELECT_TICKERS})",
            _CATEGORIES,
        )
        print("=" * 60)
        print(f"Preços cotáveis com is_manual=true a destravar: {len(rows)}")
        for r in rows:
            print(f"  {r['ticker']:12s} src={r['source']}")
        if not rows:
            print("Nada a fazer (já destravados ou sem preço).")
            return
        if not commit:
            print("\n(DRY-RUN — nada gravado. Use --commit.)")
            return
        result = await conn.execute(
            f"UPDATE asset_prices SET is_manual = false "
            f"WHERE is_manual = true AND ticker IN ({_SELECT_TICKERS})",
            _CATEGORIES,
        )
        print(f"\nOK: {result} (is_manual=false). O worker agora pode refrescar via BRAPI.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
