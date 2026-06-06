"""Registro e valoração das caixinhas/CDB do Nubank como ativos de Renda Fixa (pré-m3).

As caixinhas (RDB/CDB indexados ao CDI) saem do extrato Nubank mas não existiam no
portfólio. Aqui elas viram `asset_operations` (categoria 'Renda Fixa'), com as
operações DERIVADAS das próprias `transactions` curadas (datas + valores reais),
e valoradas via `rf_cdi.valor_atual_cdi` (CDI constante provisório — settings.cdi_anual).

Registro CONFIG-DRIVEN: adicionar uma caixinha = uma linha em CAIXINHAS. A Reserva de
Emergência (próxima a ser criada) já está listada, basta `enabled=True`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg

from engines.portfolio.migration import import_operations
from engines.portfolio.rf_cdi import valor_atual_cdi
from engines.portfolio.service import net_quantity, upsert_price

_CATEGORY = "Renda Fixa"
_PRICE_SOURCE = "nubank-cdi"


@dataclass(frozen=True)
class CaixinhaSpec:
    """Como localizar (em transactions) e valorar uma caixinha/CDB."""

    symbol: str
    broker: str
    pct_cdi: float  # 100.0 / 115.0 / 117.5
    desc_match: tuple[str, ...]  # tokens ILIKE (case-insensitive) na descrição
    source_categories: tuple[str, ...] = ("Caixinha/RDB Nubank",)
    cap: float | None = None  # informativo (ex.: Turbo R$5.000)
    enabled: bool = True


# As caixinhas ativas hoje: Snow Trip (o grosso) e Turbo (float/emergência, cap 5k).
# Reserva está zerada (próxima a criar) e HotCash encerrada — enabled=False.
CAIXINHAS: list[CaixinhaSpec] = [
    CaixinhaSpec("Nubank-SnowTrip", "Nubank", 100.0, ("snow",)),
    CaixinhaSpec("Nubank-Turbo", "Nubank", 115.0, ("turbo",), cap=5000.0),
    CaixinhaSpec("Nubank-Reserva", "Nubank", 100.0, ("reserva", "resp. ltda"), enabled=False),
    CaixinhaSpec("Nubank-HotCash", "Nubank", 100.0, ("hotcash",), enabled=False),
]

# CDB Guanabara (117,5% CDI, venc. 2028) — fonte diferente (Renda Fixa Nubank).
CDB_GUANABARA = CaixinhaSpec(
    "Guanabara-CDB",
    "Guanabara",
    117.5,
    ("guanabara",),
    source_categories=("Renda Fixa Nubank",),
)


async def build_caixinha_ops(conn: asyncpg.Connection, spec: CaixinhaSpec) -> list[dict[str, Any]]:
    """Deriva aporte/resgate (datados) das transactions que casam o spec.

    aporte = saída (amount<0); resgate = entrada (amount>0). quantidade = |amount|,
    valor_unitario = 1.0 (R$ como quantidade, igual ao seed Flash). Idempotência por
    external_id = caixinha:{symbol}:{tx.external_id} (tx external_ids são únicos).
    """
    if not spec.desc_match:
        return []
    conds = " OR ".join(
        f"description ILIKE '%' || ${i + 2} || '%'" for i in range(len(spec.desc_match))
    )
    rows = await conn.fetch(
        f"SELECT date, amount, external_id FROM transactions "
        f"WHERE category = ANY($1::text[]) AND ({conds}) ORDER BY date",
        list(spec.source_categories),
        *spec.desc_match,
    )
    ops: list[dict[str, Any]] = []
    for r in rows:
        amount = float(r["amount"])
        if amount == 0:
            continue
        tipo = "aporte" if amount < 0 else "resgate"
        ext = r["external_id"] or f"{r['date'].isoformat()}:{abs(amount):.2f}"
        ops.append(
            {
                "asset_symbol": spec.symbol,
                "asset_category": _CATEGORY,
                "tipo": tipo,
                "quantidade": abs(amount),
                "valor_unitario": 1.0,
                "data_operacao": r["date"],
                "external_id": f"caixinha:{spec.symbol}:{ext}",
            }
        )
    return ops


def compute_value(
    ops: list[dict[str, Any]], today: date, cdi_anual: float, pct_cdi: float
) -> float:
    """Valor atual da posição: aportes rendendo desde sua data, menos resgates.

    Aproximação provisória (trata o resgate como des-aporte que renderia até hoje);
    para caixinhas com pouco resgate o erro é desprezível. O m5 (série do BCB) refina.
    """
    valor = 0.0
    for op in ops:
        v = valor_atual_cdi(float(op["quantidade"]), pct_cdi, op["data_operacao"], today, cdi_anual)
        valor += v if op["tipo"] == "aporte" else -v
    return valor


async def seed_spec(
    conn: asyncpg.Connection,
    user_id: str,
    spec: CaixinhaSpec,
    today: date,
    cdi_anual: float,
) -> dict[str, Any]:
    """Registra uma caixinha: importa ops + semeia o preço (is_manual) via rf_cdi."""
    ops = await build_caixinha_ops(conn, spec)
    net = net_quantity(ops)
    value = compute_value(ops, today, cdi_anual, spec.pct_cdi)
    # Só semeia preço com posição aberta (net>0) E valor positivo. value<=0 só ocorre
    # se resgates rendessem mais que aportes (resgate datado antes do aporte) — não
    # acontece em fluxo cronológico real; o guard evita um preço negativo absurdo.
    price = value / net if net > 0 and value > 0 else 0.0
    report = {"imported": 0, "skipped": 0}
    if ops:
        report = await import_operations(conn, user_id, ops, broker_default=spec.broker)
    if price > 0:
        await upsert_price(conn, spec.symbol, price, source=_PRICE_SOURCE)
    return {
        "symbol": spec.symbol,
        "ops": len(ops),
        "imported": report["imported"],
        "skipped": report["skipped"],
        "net_principal": net,
        "valor_atual": value,
        "preco_unit": price,
    }
