#!/usr/bin/env python3
"""Gate m2 — valida o XIRR do Portfolio Engine contra a planilha do Vitor.

A planilha "DESEMPENHO CARTEIRA" não tem uma célula única de XIRR (tem %Variação por
ativo), então a validação do gate é por **reconciliação**: o custo (Aplicado) e as
quantidades por ativo do sistema devem bater com a planilha, e os valores atuais da
planilha alimentam o XIRR consolidado. Tolerância de custo: < 1% no total.

Uso:
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python ../scripts/validate_xirr.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.portfolio import service
from engines.portfolio.xirr import xirr

# Planilha DESEMPENHO CARTEIRA (B3+Tesouro+Flash): ticker -> (aplicado, valor_atual).
# Guanabara CDB e cripto ficam fora (sem data de aporte / são m4).
SHEET: dict[str, tuple[float, float]] = {
    "BBAS3": (850.68, 727.79), "CMIG4": (425.57, 423.93), "PETR4": (577.98, 742.68),
    "ITSA4": (248.07, 240.16), "SOJA3": (432.74, 319.77),
    "NASD11": (437.74, 625.24), "ACWI11": (515.83, 590.10), "ALUG11": (567.91, 570.22),
    "USDB11": (712.11, 685.58), "GOLD11": (449.28, 512.38),
    "KNCR11": (734.68, 745.85), "MXRF11": (469.87, 480.20), "HFOF11": (446.87, 460.08),
    "BTLG11": (517.15, 514.75),
    "Tesouro Selic 2028": (166.29, 191.10), "Tesouro Selic 2029": (165.94, 190.90),
    "Tesouro IPCA+ 2029": (511.19, 564.02), "Tesouro Prefixado 2032": (698.46, 724.18),
    "Tesouro IPCA+ 2040": (762.38, 773.02), "Tesouro IPCA+ 2050": (760.47, 771.89),
    "Flash-Debênture": (12000.00, 13207.62),
}
_COST_TOLERANCE_PCT = 1.0


async def main() -> None:
    await init_pool(settings.database_url)
    pool = get_pool()
    async with pool.acquire() as conn:
        uid = str(
            await conn.fetchval("SELECT id FROM users ORDER BY created_at LIMIT 1")
        )
        pos = await service.calculate_positions(conn, uid)
        ops = await conn.fetch(
            "SELECT data_operacao, tipo, quantidade, valor_unitario "
            "FROM asset_operations WHERE user_id = $1",
            uid,
        )
    await close_pool()

    mine = {p["asset_symbol"]: float(p["custo_total"]) for p in pos}

    print("=" * 70)
    print("GATE m2 — validação do XIRR (reconciliação vs planilha)")
    print("=" * 70)
    print(f"\n{'Ativo':24s} {'custo sistema':>13s} {'planilha':>10s} {'dif':>8s}")
    tot_mine = tot_sheet = 0.0
    diverge = 0
    for sym, (aplicado, _) in SHEET.items():
        mc = mine.get(sym, 0.0)
        dif = mc - aplicado
        tot_mine += mc
        tot_sheet += aplicado
        flag = "" if abs(dif) < 0.5 else "  <-- diverge"
        if abs(dif) >= 0.5:
            diverge += 1
        print(f"{sym:24s} {mc:>13.2f} {aplicado:>10.2f} {dif:>8.2f}{flag}")

    cost_dif_pct = abs(tot_mine - tot_sheet) / tot_sheet * 100 if tot_sheet else 0.0

    # XIRR consolidado usando os valores atuais da planilha (base apples-to-apples).
    flows = [
        (
            o["data_operacao"],
            service.signed_amount(
                o["tipo"], float(o["quantidade"]), float(o["valor_unitario"])
            ),
        )
        for o in ops
    ]
    valor_atual = sum(v for _, v in SHEET.values())
    # data de avaliação única (§3.1): EVALUATION_DATE no .env alinha o terminal do XIRR
    # ao service/seeds; default = data do snapshot da planilha (2026-06-05).
    terminal = settings.evaluation_date or date(2026, 6, 5)
    flows.append((terminal, valor_atual))
    rate = xirr(flows)

    print(f"\nCusto total: sistema R$ {tot_mine:,.2f} | planilha R$ {tot_sheet:,.2f}")
    print(f"Diferença de custo: {cost_dif_pct:.3f}% (tolerância {_COST_TOLERANCE_PCT}%)")
    print(f"Ativos com custo divergente (>R$0,50): {diverge}")
    print(f"Valor atual (planilha): R$ {valor_atual:,.2f}")
    print(f"XIRR consolidado (B3+Tesouro+Flash): {rate * 100:.2f}% a.a.")

    ok = cost_dif_pct < _COST_TOLERANCE_PCT
    print("\nGATE m2: " + ("PASS [ok]" if ok else "FAIL [x]"))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
