#!/usr/bin/env python3
"""Seed do CDB Banco Guanabara (117,5% CDI, venc. 2028) -> asset_operations + preço.

2 aportes de R$ 100 (R$ 200 total), derivados das transactions (categoria 'Renda
Fixa Nubank', descrição 'Compra de CDB - Banco Guanabara'). Valoração via rf_cdi.
Objetivo do ativo: segurar até o vencimento e então realocar.

Uso (a partir de api/):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      SEED_TODAY=2026-06-06 uv run python ../scripts/seed_cdb_guanabara.py [--commit]
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.portfolio import service
from engines.portfolio.caixinhas import (
    CDB_GUANABARA,
    build_caixinha_ops,
    compute_value,
    seed_spec,
)
from engines.portfolio.service import net_quantity


def _opt_today() -> str:
    if "--today" in sys.argv:
        i = sys.argv.index("--today")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.environ.get("SEED_TODAY", "2026-06-06")


def main() -> None:
    commit = "--commit" in sys.argv
    today = date.fromisoformat(_opt_today())

    print("=" * 70)
    print("SEED CDB BANCO GUANABARA (117,5% CDI, venc. 2028)")
    print("=" * 70)
    print(f"\nCDI ref: {settings.cdi_anual * 100:.2f}% a.a. | data ref: {today}")

    async def _run() -> None:
        await init_pool(settings.database_url)
        async with get_pool().acquire() as conn:
            admin = await conn.fetchrow("SELECT id, email FROM users ORDER BY created_at LIMIT 1")
            if not admin:
                print("[erro] Nenhum usuário no banco.")
                sys.exit(1)
            user_id = str(admin["id"])
            if commit:
                r = await seed_spec(conn, user_id, CDB_GUANABARA, today, settings.cdi_anual)
                await service.invalidate_xirr_cache(user_id)
            else:
                ops = await build_caixinha_ops(conn, CDB_GUANABARA)
                net = net_quantity(ops)
                val = compute_value(ops, today, settings.cdi_anual, CDB_GUANABARA.pct_cdi)
                r = {
                    "symbol": CDB_GUANABARA.symbol, "ops": len(ops), "imported": 0,
                    "net_principal": net, "valor_atual": val,
                    "preco_unit": (val / net if net > 0 else 0.0),
                }
            print(
                f"  {r['symbol']:<16} ops={r['ops']:>3}  net=R$ {r['net_principal']:>8.2f}"
                f"  valor=R$ {r['valor_atual']:>8.2f}  preço={r['preco_unit']:.4f}"
                + (f"  (+{r['imported']} novas)" if commit else "")
            )
            if commit:
                print(f"\nUsuário: {admin['email']}")
        await close_pool()

    if not commit:
        print("\n(DRY-RUN — nada gravado. Use --commit para gravar.)")
    asyncio.run(_run())
    print("=" * 70)


if __name__ == "__main__":
    main()
