#!/usr/bin/env python3
"""Migração de OPERAÇÕES (planilha CSV) -> asset_operations + validação XIRR.

STORY-02-17-18 (gate crítico de m2). Importa o histórico de operações da aba
OPERAÇÕES e valida que o XIRR Python coincide com o XIRR do Excel (< 0,1 pp).

Formato esperado do CSV (cabeçalho; aliases aceitos, sem acento/maiúsculas):
    data,ticker,categoria,tipo,quantidade,preco_unitario,total
- data: YYYY-MM-DD ou DD/MM/YYYY
- categoria: ACOES | ETF | FII | RENDA_FIXA | APOSENTADORIA | CRIPTO
- tipo: buy | sell | income  (ou compra/venda/dividendo/juros/aporte/resgate)
- Renda Fixa pode vir sem quantidade (importa por valor total).

Uso:
    uv run python ../scripts/migrate_portfolio.py <csv> [--dry-run]
    uv run python ../scripts/migrate_portfolio.py <csv> --excel-xirr 0.0853 [--tolerance 0.001]

ATENÇÃO (definir antes de rodar no CSV real):
- Sinal das compras na planilha (o storage usa quantidade>0 + tipo; o sinal do
  XIRR é aplicado no cálculo, então o sinal da planilha não afeta o import).
- Cripto em USD vs BRL: converter para BRL antes (ou exportar já em BRL).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from collections import Counter

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.portfolio import service
from engines.portfolio.migration import import_operations, parse_operations_csv


def _arg(flag: str) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


async def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print("Uso: migrate_portfolio.py <csv> [--dry-run] [--excel-xirr X]")
        sys.exit(2)

    csv_path = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv
    excel_xirr = _arg("--excel-xirr")
    tolerance = float(_arg("--tolerance") or "0.001")  # 0,1 pp

    print("=" * 70)
    print("MIGRAÇÃO PORTFOLIO — aba OPERAÇÕES (gate m2)")
    print("=" * 70)

    text = csv_path.read_text(encoding="utf-8-sig")  # noqa: ASYNC240 (CLI one-shot)
    rows = parse_operations_csv(text)

    by_tipo = Counter(r["tipo"] for r in rows)
    by_cat = Counter(r["asset_category"] for r in rows)
    print(f"\nLinhas parseadas: {len(rows)}")
    print(f"  por tipo:      {dict(by_tipo)}")
    print(f"  por categoria: {dict(by_cat)}")

    if dry_run:
        print("\n(dry-run — nenhuma alteração no banco)")
        return

    try:
        await init_pool(settings.database_url)
        pool = get_pool()
        async with pool.acquire() as conn:
            admin = await conn.fetchrow(
                "SELECT id, email FROM users ORDER BY created_at LIMIT 1"
            )
            if not admin:
                print("[erro] Nenhum usuário no banco. Crie um usuário primeiro.")
                sys.exit(1)
            user_id = str(admin["id"])
            print(f"\nUsuário: {admin['email']} (id={user_id})")

            report = await import_operations(conn, user_id, rows)
            await service.invalidate_xirr_cache(user_id)
            xirr_result = await service.calculate_portfolio_xirr(conn, user_id)

        consolidated = xirr_result["consolidated"]
        print(f"\nImportadas: {report['imported']} | Já existentes: {report['skipped']}")
        print(
            "XIRR consolidado (Python): "
            + (f"{consolidated:.6f} ({consolidated * 100:.2f}% a.a.)"
               if consolidated is not None else "indefinido (sem fluxos suficientes)")
        )

        if excel_xirr is not None and consolidated is not None:
            diff = abs(consolidated - float(excel_xirr))
            ok = diff < tolerance
            print(f"XIRR Excel (ref):          {float(excel_xirr):.6f}")
            print(f"Diferença:                 {diff * 100:.4f} pp "
                  f"(tolerância {tolerance * 100:.2f} pp)")
            print("GATE: " + ("PASS [ok]" if ok else "FAIL [x] — investigar"))
            if not ok:
                sys.exit(1)
    finally:
        await close_pool()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
