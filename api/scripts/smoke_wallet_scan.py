"""Smoke ao vivo do scan de wallets (m4). Roda 1 scan + precifica + lista valorado.

Uso pontual no ambiente do Vitor (lê o .env real). NÃO imprime endereços/segredos —
só chain / ativo / quantidade / valor BRL. `uv run python scripts/smoke_wallet_scan.py`.
"""
from __future__ import annotations

import asyncio

from db.connection import close_pool, init_pool
from engines.wallet.service import list_wallet_positions
from workers.price_workers import run_price_crypto
from workers.wallet_workers import resolve_owner_id, run_wallet_scan


async def main() -> None:
    pool = await init_pool()
    try:
        uid = await resolve_owner_id(pool)
        if uid is None:
            print("sem usuário no banco — abortando")
            return

        print("== SCAN (6 fetchers reais) ==")
        stats = await run_wallet_scan(pool, uid)
        for name, s in stats.items():
            print(
                f"  {name:18s} fetched={s['fetched']} failed={s['failed']} swept={s['swept']}"
            )

        print("== PREÇO cripto (CoinGecko, m3) ==")
        pc = await run_price_crypto(pool)
        print(f"  {pc}")

        print("== POSIÇÕES VALORADAS (sem endereços) ==")
        async with pool.acquire() as conn:
            rows = await list_wallet_positions(conn, uid)
        total = 0.0
        for r in rows:
            v = r["value_brl"]
            total += v or 0.0
            vs = f"R$ {v:,.2f}" if v is not None else "— (sem preço)"
            stale = "  [STALE]" if r["stale"] else ""
            print(
                f"  {r['chain']:12s} {r['asset_symbol']:8s} "
                f"qty={r['quantity']:.8f}  {vs}{stale}"
            )
        print(f"  ---\n  TOTAL valorado: R$ {total:,.2f}   ({len(rows)} posições)")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
