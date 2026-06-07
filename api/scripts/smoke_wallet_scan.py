"""Smoke ao vivo do scan de wallets (m4). Roda 1 scan + precifica + lista valorado.

Uso pontual no ambiente do Vitor (lê o .env real). NÃO imprime endereços/segredos —
só chain / ativo / quantidade / valor BRL. `uv run python scripts/smoke_wallet_scan.py`.
"""
from __future__ import annotations

import asyncio

from db.connection import close_pool, init_pool
from engines.wallet.service import list_wallet_positions, prices_by_ticker
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
        total_brl = total_usd = 0.0
        for r in rows:
            v, vu = r["value_brl"], r["value_usd"]
            total_brl += v or 0.0
            total_usd += vu or 0.0
            vs = f"R$ {v:,.2f}" if v is not None else "— (sem preço)"
            us = f" / $ {vu:,.2f}" if vu is not None else ""
            stale = "  [STALE]" if r["stale"] else ""
            print(
                f"  {r['chain']:12s} {r['asset_symbol']:10s} "
                f"qty={r['quantity']:.8f}  {vs}{us}{stale}"
            )
        print(
            f"  ---\n  TOTAL carteira: R$ {total_brl:,.2f} / $ {total_usd:,.2f}"
            f"   ({len(rows)} posições)"
        )

        print("== DeFi VALORADO (sem endereços) ==")
        async with pool.acquire() as conn:
            drows = await conn.fetch(
                "SELECT asset_symbol, balance FROM defi_positions "
                "WHERE user_id = $1 AND is_active ORDER BY asset_symbol",
                uid,
            )
            dprices = await prices_by_ticker(conn, [d["asset_symbol"] for d in drows])
        dtotal_brl = dtotal_usd = 0.0
        for d in drows:
            bal = float(d["balance"])
            brl, usd = dprices.get(d["asset_symbol"], (None, None))
            vb = bal * brl if brl is not None else None
            vu = bal * usd if usd is not None else None
            dtotal_brl += vb or 0.0
            dtotal_usd += vu or 0.0
            vs = f"R$ {vb:,.2f}" if vb is not None else "— (sem preço)"
            us = f" / $ {vu:,.2f}" if vu is not None else ""
            print(f"  {d['asset_symbol']:16s} bal={bal:.6f}  {vs}{us}")
        print(
            f"  ---\n  TOTAL DeFi: R$ {dtotal_brl:,.2f} / $ {dtotal_usd:,.2f}"
            f"   ({len(drows)} posições)"
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
