#!/usr/bin/env python3
"""Seed das caixinhas Nubank (RF pós-fixada % CDI) -> asset_operations + preço.

Deriva as operações (aporte/resgate datados) das `transactions` curadas e valora
via rf_cdi (settings.cdi_anual, provisório até o m5). Registra cada caixinha ATIVA
do registro `engines.portfolio.caixinhas.CAIXINHAS`.

Uso (a partir de api/):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      SEED_TODAY=2026-06-06 uv run python ../scripts/seed_caixinhas.py [--commit]
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
from engines.portfolio.caixinhas import CAIXINHAS, build_caixinha_ops, compute_value, seed_spec


def _opt_today() -> str:
    if "--today" in sys.argv:
        i = sys.argv.index("--today")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    if env := os.environ.get("SEED_TODAY"):
        return env
    # §3.1: alinha a data de avaliação ao service/validator via settings.evaluation_date.
    return settings.evaluation_date.isoformat() if settings.evaluation_date else "2026-06-06"


def main() -> None:
    commit = "--commit" in sys.argv
    today = date.fromisoformat(_opt_today())
    active = [c for c in CAIXINHAS if c.enabled]

    print("=" * 70)
    print("SEED CAIXINHAS NUBANK (RF pós-fixada % CDI)")
    print("=" * 70)
    print(f"\nCDI ref: {settings.cdi_anual * 100:.2f}% a.a. | data ref: {today}")
    print(f"Ativas: {', '.join(c.symbol for c in active)}")

    async def _run() -> None:
        await init_pool(settings.database_url)
        async with get_pool().acquire() as conn:
            admin = await conn.fetchrow("SELECT id, email FROM users ORDER BY created_at LIMIT 1")
            if not admin:
                print("[erro] Nenhum usuário no banco.")
                sys.exit(1)
            user_id = str(admin["id"])
            for spec in active:
                if commit:
                    r = await seed_spec(conn, user_id, spec, today, settings.cdi_anual)
                else:
                    ops = await build_caixinha_ops(conn, spec)
                    from engines.portfolio.service import net_quantity

                    net = net_quantity(ops)
                    val = compute_value(ops, today, settings.cdi_anual, spec.pct_cdi)
                    r = {
                        "symbol": spec.symbol, "ops": len(ops), "imported": 0,
                        "net_principal": net, "valor_atual": val,
                        "preco_unit": (val / net if net > 0 else 0.0),
                    }
                print(
                    f"  {r['symbol']:<16} ops={r['ops']:>3}  net=R$ {r['net_principal']:>10.2f}"
                    f"  valor=R$ {r['valor_atual']:>10.2f}  preço={r['preco_unit']:.4f}"
                    + (f"  (+{r['imported']} novas)" if commit else "")
                )
            if commit:
                await service.invalidate_xirr_cache(user_id)
                print(f"\nUsuário: {admin['email']}")
        await close_pool()

    if not commit:
        print("\n(DRY-RUN — nada gravado. Use --commit para gravar.)")
    asyncio.run(_run())
    print("=" * 70)


if __name__ == "__main__":
    main()
