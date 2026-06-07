"""Crypto sleeve (m4) — bridge fiel entre o ledger (custo BRL) e as carteiras (valor atual).

Cripto NÃO vive em `asset_operations`: o BRL do ledger não tem ativo/quantidade por linha;
linhas sintéticas corromperiam `_dca_price`, o IR-cripto e o `reconcile()` por quantidade.
Este módulo cruza as duas fontes de verdade já existentes:
- **valor atual** (user-scoped): `wallet_positions` + `defi_positions`, valorados pelo cache
  de preço do m3 (reuso de `list_wallet_positions`/`list_defi_valued`).
- **custo/cashflows** (BRL): `transactions` nas categorias cripto do ledger
  (`settings.crypto_ledger_categories`).

O custo/resultado/XIRR são conhecidos só no NÍVEL DO SLEEVE (cripto como um bucket) — fiel à
reconciliação estilo "caixa parado na Toro" (caixa enviado vs posição atual). NUNCA fabricar
retorno por ativo (CLAUDE.md: usar XIRR, não `(resultado-aplicado)/aplicado`).

Import lazy a partir de `portfolio.service` (evita ciclo: `wallet.service` já importa
`portfolio.service.net_quantity`).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import asyncpg

from config import settings
from engines.wallet.service import list_defi_valued, list_wallet_positions

from .constants import AssetCategory
from .service import _nan_to_none, eval_date
from .xirr import xirr


async def sleeve_cost_basis(conn: asyncpg.Connection) -> dict[str, Any]:
    """Custo do sleeve a partir do ledger (global/single-user; `transactions` não tem user_id).

    `cost_basis` = Σ|saídas| (amount<0); `returned` = Σ entradas (amount>0);
    `net_invested` = cost_basis - returned. `by_category` traz o investido líquido por rail.
    """
    rows = await conn.fetch(
        "SELECT category, amount FROM transactions WHERE category = ANY($1::text[])",
        settings.crypto_ledger_categories,
    )
    cost_basis = 0.0
    returned = 0.0
    by_category: dict[str, float] = defaultdict(float)
    for r in rows:
        amt = float(r["amount"])
        if amt < 0:
            cost_basis += -amt
        else:
            returned += amt
        by_category[r["category"]] += -amt  # saída (negativa) → investido positivo
    return {
        "cost_basis_brl": cost_basis,
        "returned_brl": returned,
        "net_invested_brl": cost_basis - returned,
        "by_category": [
            {"category": c, "net_invested_brl": v}
            for c, v in sorted(by_category.items())
        ],
    }


async def sleeve_cashflows(conn: asyncpg.Connection) -> list[tuple[date, float]]:
    """Série de cashflows do ledger cripto (sinais crus: aporte<0, retorno>0)."""
    rows = await conn.fetch(
        "SELECT date, amount FROM transactions WHERE category = ANY($1::text[]) "
        "ORDER BY date",
        settings.crypto_ledger_categories,
    )
    return [(r["date"], float(r["amount"])) for r in rows]


async def sleeve_current_value(
    conn: asyncpg.Connection, user_id: str
) -> tuple[float, dict[str, float], bool]:
    """Valor atual do sleeve (BRL) + por rail + `stale` (alguma posição sem preço).

    Wallets agrupadas por `chain`; DeFi sob o rail "defi". Sem preço → contribui 0 e
    marca `stale=True` (fail-soft; nunca levanta por falta de preço).
    """
    wallets = await list_wallet_positions(conn, user_id)
    defi = await list_defi_valued(conn, user_id)
    total = 0.0
    by_rail: dict[str, float] = defaultdict(float)
    stale = False
    for w in wallets:
        v = w["value_brl"]
        if v is None:
            stale = True
            continue
        total += v
        by_rail[w["chain"]] += v
    for d in defi:
        v = d["value_brl"]
        if v is None:
            stale = True
            continue
        total += v
        by_rail["defi"] += v
    return total, dict(by_rail), stale


async def crypto_positions(
    conn: asyncpg.Connection, user_id: str
) -> list[dict[str, Any]]:
    """Linhas de posição cripto AGREGADAS por ativo p/ a aba Posições (m4).

    Mesmo shape de `calculate_positions`, mas custo é desconhecido por ativo → `preco_medio`/
    `custo_total`/`resultado`/`resultado_pct = None` (custo/resultado vivem no nível do sleeve;
    nunca fabricar retorno por ativo). Agrega o mesmo símbolo em várias chains numa linha
    (detalhe por-chain fica na aba Carteiras). Sem preço → `stale=True`, `valor_atual=None`.
    """
    wallets = await list_wallet_positions(conn, user_id)
    defi = await list_defi_valued(conn, user_id)
    agg: dict[str, dict[str, Any]] = {}
    for w in wallets:
        _accumulate(agg, w["asset_symbol"], float(w["quantity"]), w["price_brl"])
    for d in defi:
        _accumulate(agg, d["asset_symbol"], float(d["balance"]), d["price_brl"])

    out: list[dict[str, Any]] = []
    for sym, a in agg.items():
        qty = a["qty"]
        if qty <= 0:
            continue
        price = a["price"]
        out.append(
            {
                "asset_symbol": sym,
                "asset_category": str(AssetCategory.CRIPTO),
                "quantidade_net": qty,
                "preco_medio": None,
                "custo_total": None,
                "preco_atual": price,
                "valor_atual": qty * price if price is not None else None,
                "resultado": None,
                "resultado_pct": None,
                "stale": price is None,
                # preço vem do Market Engine (cripto = CoinGecko) → não editável aqui
                "is_manual": False,
            }
        )
    return out


def _accumulate(
    agg: dict[str, dict[str, Any]], sym: str, qty: float, price: float | None
) -> None:
    a = agg.setdefault(sym, {"qty": 0.0, "price": None})
    a["qty"] += qty
    if price is not None:
        a["price"] = price


async def calculate_crypto_sleeve(
    conn: asyncpg.Connection, user_id: str, today: date | None = None
) -> dict[str, Any]:
    """Resumo do sleeve cripto: custo (ledger) vs valor atual (carteiras) → resultado + XIRR.

    Também serve a reconciliação de VALOR (net_invested vs current_value → resultado, por rail).
    XIRR = `xirr(cashflows do ledger + (today, +valor_atual))`; None com <2 fluxos ou sem
    convergência (`_nan_to_none`).
    """
    today = eval_date(today)
    total, by_rail, stale = await sleeve_current_value(conn, user_id)
    cost = await sleeve_cost_basis(conn)
    flows = await sleeve_cashflows(conn)
    if total > 0:
        flows = [*flows, (today, total)]
    rate = _nan_to_none(xirr(flows)) if len(flows) >= 2 else None
    return {
        "current_value_brl": total,
        "cost_basis_brl": cost["cost_basis_brl"],
        "returned_brl": cost["returned_brl"],
        "net_invested_brl": cost["net_invested_brl"],
        "resultado": total - cost["net_invested_brl"],
        "xirr": rate,
        "by_rail": [
            {"rail": k, "current_value_brl": v} for k, v in sorted(by_rail.items())
        ],
        "by_category": cost["by_category"],
        "stale_value": stale,
    }
