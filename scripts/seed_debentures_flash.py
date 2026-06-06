#!/usr/bin/env python3
"""Seed das debêntures Flash (RF pré-fixada) -> asset_operations + preço atual.

Lê files/debentures-flash/integralizacoes.json (12 integralizações de R$ 1.000,
"Pré 24% a.a.", fator mensal 1,78%). Cada integralização vira um `aporte` em
asset_operations (asset_symbol='Flash-Debênture', categoria 'Renda Fixa',
quantidade=valor, valor_unitario=1.0). O preço atual unitário é semeado em
asset_prices = valor_atual_total / total_aplicado (valoração pré-fixada).

Uso:
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python ../scripts/seed_debentures_flash.py [--dry-run] [--commit]
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.portfolio import service
from engines.portfolio.migration import import_operations
from engines.portfolio.rf_pre import valor_atual_pre

_JSON = Path(__file__).parent.parent / "files" / "debentures-flash" / "integralizacoes.json"
_SYMBOL = "Flash-Debênture"
_CATEGORY = "Renda Fixa"


def _parse_fator(indice_nome: str, fator: str) -> float:
    """Fator mensal (%) — do JSON 'fator' (ex.: '1.780000' -> 1.78)."""
    return float(fator)


def _build(today: date) -> tuple[list[dict], float, float]:
    data = json.loads(_JSON.read_text(encoding="utf-8"))
    ops: list[dict] = []
    total_aplicado = 0.0
    valor_atual = 0.0
    for item in data:
        d = date.fromisoformat(item["data"])
        principal = float(item["valor"])
        fator_mes = _parse_fator(item["indice_nome"], item["fator"])
        total_aplicado += principal
        valor_atual += valor_atual_pre(principal, fator_mes, d, today)
        ops.append(
            {
                "asset_symbol": _SYMBOL,
                "asset_category": _CATEGORY,
                "tipo": "aporte",
                "quantidade": principal,  # R$ aplicados como "quantidade"
                "valor_unitario": 1.0,
                "data_operacao": d,
                "external_id": f"flash-deb:{item['data']}",
            }
        )
    return ops, total_aplicado, valor_atual


def main() -> None:
    dry_run = "--dry-run" in sys.argv or "--commit" not in sys.argv
    today = date.fromisoformat(_opt_today())

    ops, aplicado, atual = _build(today)
    preco_unit = atual / aplicado if aplicado else 0.0

    print("=" * 70)
    print("SEED DEBÊNTURES FLASH (RF pré-fixada)")
    print("=" * 70)
    print(f"\nIntegralizações: {len(ops)} | data ref: {today}")
    print(f"Total aplicado:  R$ {aplicado:,.2f}")
    print(f"Valor atual:     R$ {atual:,.2f}  (+{(atual/aplicado-1)*100:.2f}%)")
    print(f"Preço unitário (asset_prices['{_SYMBOL}']): {preco_unit:.6f}")

    if dry_run:
        print("\n(DRY-RUN — nada gravado. Use --commit para gravar.)")
        return

    import asyncio

    async def _run() -> None:
        await init_pool(settings.database_url)
        pool = get_pool()
        async with pool.acquire() as conn:
            admin = await conn.fetchrow(
                "SELECT id, email FROM users ORDER BY created_at LIMIT 1"
            )
            if not admin:
                print("[erro] Nenhum usuário no banco.")
                sys.exit(1)
            user_id = str(admin["id"])
            report = await import_operations(conn, user_id, ops, broker_default="Flash")
            await service.upsert_price(conn, _SYMBOL, preco_unit, source="flash-pre")
            await service.invalidate_xirr_cache(user_id)
        await close_pool()
        print(f"\nUsuário: {admin['email']}")
        print(f"Importadas: {report['imported']} | Já existentes: {report['skipped']}")

    asyncio.run(_run())
    print("=" * 70)


def _opt_today() -> str:
    if "--today" in sys.argv:
        i = sys.argv.index("--today")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    import os

    if env := os.environ.get("SEED_TODAY"):
        return env
    # §3.1: alinha a data de avaliação ao service/validator via settings.evaluation_date.
    return settings.evaluation_date.isoformat() if settings.evaluation_date else "2026-06-05"


if __name__ == "__main__":
    main()
