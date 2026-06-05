"""Portfolio service — lógica de negócio e orquestração (m2).

Funções puras testáveis (cashflows, rebalanceamento) + orquestração sobre asyncpg.
Cálculos:
- XIRR por ativo, por categoria e consolidado (STORY-02-06) — usa `xirr.py`.
- Posições atuais valoradas com preço manual (STORY-02-07).
- Alocação vs meta (STORY-02-08), rebalanceamento (STORY-02-09),
  rendimentos (STORY-02-10), IR RV (STORY-02-11), IR cripto (STORY-02-12).

Sinais do cashflow (ADR-002 / CLAUDE.md):
- compra/aporte -> saida de caixa (negativo)
- venda/resgate/dividendo/juros -> entrada (positivo)
- posicao atual -> entrada positiva na data de hoje (qtd_net * preco manual)
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from engines.market.cache import PriceCache

from .xirr import xirr

# Tipos que aumentam posição (entram no DCA e no quantidade_net positivo)
_INFLOW_TIPOS = ("compra", "aporte")
# Tipos que reduzem posição
_OUTFLOW_TIPOS = ("venda", "resgate")
# Rendimentos — entram no XIRR como caixa positivo, mas não alteram quantidade
_INCOME_TIPOS = ("dividendo", "juros")

_XIRR_TTL_SECONDS = 3600  # 1h (ADR-008)

_cache = PriceCache()


# --------------------------------------------------------------------------- #
# Cashflows / XIRR (funções puras + orquestração)
# --------------------------------------------------------------------------- #
def signed_amount(tipo: str, quantidade: float, valor_unitario: float) -> float:
    """Valor com sinal do cashflow: compra/aporte negativo, demais positivo."""
    total = quantidade * valor_unitario
    return -total if tipo in _INFLOW_TIPOS else total


def net_quantity(ops: Sequence[Any]) -> float:
    """Quantidade liquida: soma(compra,aporte) - soma(venda,resgate)."""
    qty = 0.0
    for op in ops:
        tipo = op["tipo"]
        if tipo in _INFLOW_TIPOS:
            qty += float(op["quantidade"])
        elif tipo in _OUTFLOW_TIPOS:
            qty -= float(op["quantidade"])
    return qty


def build_cashflows(
    ops: Sequence[Any], current_value: float | None, today: date
) -> list[tuple[date, float]]:
    """Constrói a série de cashflows de um conjunto de operações.

    Adiciona a posição atual (valor de mercado) como entrada positiva em `today`
    quando `current_value` é conhecido e positivo.
    """
    flows: list[tuple[date, float]] = [
        (
            op["data_operacao"],
            signed_amount(
                op["tipo"], float(op["quantidade"]), float(op["valor_unitario"])
            ),
        )
        for op in ops
    ]
    if current_value is not None and current_value > 0:
        flows.append((today, current_value))
    return flows


def _nan_to_none(value: float) -> float | None:
    """XIRR devolve nan para <2 fluxos / não-convergência → None (JSON-safe)."""
    return None if math.isnan(value) else value


def _sum_or_none(values: Sequence[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


async def fetch_prices(conn: asyncpg.Connection) -> dict[str, float]:
    """Carrega o último preço (BRL) por ticker de asset_prices."""
    rows = await conn.fetch("SELECT ticker, price_brl FROM asset_prices")
    return {row["ticker"]: float(row["price_brl"]) for row in rows}


async def upsert_price(
    conn: asyncpg.Connection,
    ticker: str,
    price_brl: float,
    *,
    source: str = "manual",
    is_manual: bool = True,
) -> dict[str, Any]:
    """Insere/atualiza o preço manual de um ticker (upsert por PK ticker)."""
    row = await conn.fetchrow(
        """
        INSERT INTO asset_prices (ticker, price_brl, source, is_manual, fetched_at)
        VALUES ($1, $2, $3, $4, now())
        ON CONFLICT (ticker) DO UPDATE
          SET price_brl = EXCLUDED.price_brl,
              source = EXCLUDED.source,
              is_manual = EXCLUDED.is_manual,
              fetched_at = now()
        RETURNING ticker, price_brl, price_usd, source, is_manual, fetched_at
        """,
        ticker,
        price_brl,
        source,
        is_manual,
    )
    return dict(row) if row else {}


def _xirr_key(user_id: str) -> str:
    return f"xirr:consolidated:{user_id}"


async def invalidate_xirr_cache(user_id: str) -> None:
    """Invalida o cache de XIRR do usuário (chamado nos mutadores de operação)."""
    await _cache.delete(_xirr_key(user_id))


async def calculate_portfolio_xirr(
    conn: asyncpg.Connection, user_id: str, today: date | None = None
) -> dict[str, Any]:
    """XIRR por ativo, por categoria e consolidado. Cacheado 1h (ADR-008)."""
    cached = await _cache.get(_xirr_key(user_id))
    if cached is not None:
        return dict(cached)

    today = today or date.today()
    ops = await conn.fetch(
        """
        SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario,
               data_operacao
        FROM asset_operations
        WHERE user_id = $1
        ORDER BY data_operacao
        """,
        user_id,
    )
    prices = await fetch_prices(conn)

    by_asset_ops: dict[str, list[Any]] = defaultdict(list)
    by_cat_ops: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_asset_ops[op["asset_symbol"]].append(op)
        by_cat_ops[op["asset_category"]].append(op)

    # Por ativo + valor atual de cada ativo (qtd_net * preco manual)
    by_asset: dict[str, float | None] = {}
    asset_current: dict[str, float | None] = {}
    for sym, aops in by_asset_ops.items():
        price = prices.get(sym)
        cur = net_quantity(aops) * price if price is not None else None
        asset_current[sym] = cur
        by_asset[sym] = _nan_to_none(xirr(build_cashflows(aops, cur, today)))

    # Por categoria (soma dos valores atuais dos ativos da categoria)
    by_category: dict[str, float | None] = {}
    for cat, cops in by_cat_ops.items():
        syms = {op["asset_symbol"] for op in cops}
        cat_cur = _sum_or_none([asset_current.get(s) for s in syms])
        by_category[cat] = _nan_to_none(xirr(build_cashflows(cops, cat_cur, today)))

    # Consolidado
    total_cur = _sum_or_none(list(asset_current.values()))
    consolidated = _nan_to_none(xirr(build_cashflows(list(ops), total_cur, today)))

    result: dict[str, Any] = {
        "consolidated": consolidated,
        "by_category": by_category,
        "by_asset": by_asset,
        "calculated_at": datetime.now(tz=UTC).isoformat(),
    }
    await _cache.set(_xirr_key(user_id), result, _XIRR_TTL_SECONDS)
    return result
