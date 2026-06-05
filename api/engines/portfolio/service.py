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


# --------------------------------------------------------------------------- #
# Posições (STORY-02-07)
# --------------------------------------------------------------------------- #
def _dca_price(ops: Sequence[Any]) -> float:
    """Preco medio ponderado de compra/aporte (custo / quantidade)."""
    qty = sum(
        float(o["quantidade"]) for o in ops if o["tipo"] in _INFLOW_TIPOS
    )
    cost = sum(
        float(o["quantidade"]) * float(o["valor_unitario"])
        for o in ops
        if o["tipo"] in _INFLOW_TIPOS
    )
    return cost / qty if qty else 0.0


async def calculate_positions(
    conn: asyncpg.Connection, user_id: str
) -> list[dict[str, Any]]:
    """Posicao atual por ativo, valorada com preco manual (asset_prices).

    Inclui apenas ativos com quantidade liquida > 0 (posicoes abertas).
    Sem preco -> valor_atual/resultado null e stale=true (ADR-004).
    """
    ops = await conn.fetch(
        """
        SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario
        FROM asset_operations
        WHERE user_id = $1
        """,
        user_id,
    )
    prices = await fetch_prices(conn)

    by_asset: dict[str, list[Any]] = defaultdict(list)
    category_of: dict[str, str] = {}
    for op in ops:
        by_asset[op["asset_symbol"]].append(op)
        category_of[op["asset_symbol"]] = op["asset_category"]

    positions: list[dict[str, Any]] = []
    for sym, aops in by_asset.items():
        qty_net = net_quantity(aops)
        if qty_net <= 0:
            continue
        preco_medio = _dca_price(aops)
        custo_total = preco_medio * qty_net
        price = prices.get(sym)
        valor_atual: float | None = None
        resultado: float | None = None
        resultado_pct: float | None = None
        stale = True
        if price is not None:
            valor_atual = qty_net * price
            resultado = valor_atual - custo_total
            resultado_pct = resultado / custo_total * 100 if custo_total else 0.0
            stale = False
        positions.append(
            {
                "asset_symbol": sym,
                "asset_category": category_of[sym],
                "quantidade_net": qty_net,
                "preco_medio": preco_medio,
                "custo_total": custo_total,
                "preco_atual": price,
                "valor_atual": valor_atual,
                "resultado": resultado,
                "resultado_pct": resultado_pct,
                "stale": stale,
            }
        )
    positions.sort(key=lambda p: str(p["asset_symbol"]))
    return positions


# --------------------------------------------------------------------------- #
# Alocacao atual vs meta (STORY-02-08)
# --------------------------------------------------------------------------- #
async def calculate_allocation(
    conn: asyncpg.Connection, user_id: str
) -> dict[str, Any]:
    """Alocacao atual (valor de mercado) vs meta por categoria + desvio em pp.

    Categorias = uniao das categorias com posicao e das metas seedadas.
    `pct_meta`/`desvio_pp` ficam null para categorias sem meta definida.
    """
    positions = await calculate_positions(conn, user_id)
    target_rows = await conn.fetch(
        "SELECT category, target_pct FROM portfolio_targets WHERE user_id = $1",
        user_id,
    )
    target_map = {row["category"]: float(row["target_pct"]) for row in target_rows}

    value_by_cat: dict[str, float] = defaultdict(float)
    for pos in positions:
        if pos["valor_atual"] is not None:
            value_by_cat[pos["asset_category"]] += float(pos["valor_atual"])
    total = sum(value_by_cat.values())

    categories: list[dict[str, Any]] = []
    for cat in sorted(set(value_by_cat) | set(target_map)):
        valor = value_by_cat.get(cat, 0.0)
        pct_atual = valor / total * 100 if total else 0.0
        pct_meta = target_map.get(cat)
        desvio_pp = pct_atual - pct_meta if pct_meta is not None else None
        categories.append(
            {
                "category": cat,
                "valor_atual": valor,
                "pct_atual": pct_atual,
                "pct_meta": pct_meta,
                "desvio_pp": desvio_pp,
            }
        )
    return {"total": total, "categories": categories}


# --------------------------------------------------------------------------- #
# Rebalanceamento (STORY-02-09)
# --------------------------------------------------------------------------- #
def suggest_rebalancing(
    value_by_cat: dict[str, float],
    target_map: dict[str, float],
    contribution: float,
) -> dict[str, float]:
    """Distribui `contribution` para as categorias abaixo do alvo (nunca vende).

    Pseudocodigo da Arquitetura secao 7: gap = meta% * (total+aporte) - valor_atual;
    so categorias com gap positivo recebem aporte, proporcional ao gap.
    Retorna {} quando nao ha gap positivo (tudo no alvo/acima) ou aporte <= 0.
    """
    if contribution <= 0:
        return {}
    total = sum(value_by_cat.values()) + contribution
    gaps = {
        cat: pct / 100 * total - value_by_cat.get(cat, 0.0)
        for cat, pct in target_map.items()
    }
    positive = {cat: gap for cat, gap in gaps.items() if gap > 0}
    total_gap = sum(positive.values())
    if total_gap <= 0:
        return {}
    return {cat: contribution * gap / total_gap for cat, gap in positive.items()}


async def calculate_rebalancing(
    conn: asyncpg.Connection, user_id: str, contribution: float
) -> dict[str, Any]:
    """Sugestao de aporte dado um valor de entrada, com contexto de alocacao."""
    alloc = await calculate_allocation(conn, user_id)
    cats = alloc["categories"]
    value_by_cat = {c["category"]: float(c["valor_atual"]) for c in cats}
    target_map = {
        c["category"]: float(c["pct_meta"])
        for c in cats
        if c["pct_meta"] is not None
    }
    suggestions = suggest_rebalancing(value_by_cat, target_map, contribution)

    result: dict[str, Any] = {
        "contribution": contribution,
        "suggestions": suggestions,
        "current_allocation": {c["category"]: c["pct_atual"] for c in cats},
        "target_allocation": target_map,
        "deviations_pp": {
            c["category"]: c["desvio_pp"]
            for c in cats
            if c["desvio_pp"] is not None
        },
    }
    if not suggestions:
        result["message"] = (
            "Todas as categorias estao no alvo ou acima — nenhum aporte sugerido."
        )
    return result


# --------------------------------------------------------------------------- #
# Rendimentos: dividendos / juros (STORY-02-10)
# --------------------------------------------------------------------------- #
async def calculate_income(
    conn: asyncpg.Connection,
    user_id: str,
    data_from: date | None = None,
    data_to: date | None = None,
) -> dict[str, Any]:
    """Rendimentos (tipo dividendo/juros), separados de ganho de capital.

    Valor de cada rendimento = quantidade * valor_unitario. Opcionalmente filtra
    por periodo [data_from, data_to].
    """
    query = """
        SELECT asset_symbol, asset_category, tipo, quantidade, valor_unitario
        FROM asset_operations
        WHERE user_id = $1 AND tipo IN ('dividendo', 'juros')
    """
    params: list[Any] = [user_id]
    idx = 2
    if data_from is not None:
        query += f" AND data_operacao >= ${idx}"
        params.append(data_from)
        idx += 1
    if data_to is not None:
        query += f" AND data_operacao <= ${idx}"
        params.append(data_to)
        idx += 1

    rows = await conn.fetch(query, *params)

    by_asset: dict[str, float] = defaultdict(float)
    by_category: dict[str, float] = defaultdict(float)
    by_type: dict[str, float] = defaultdict(float)
    category_of: dict[str, str] = {}
    total = 0.0
    for row in rows:
        value = float(row["quantidade"]) * float(row["valor_unitario"])
        by_asset[row["asset_symbol"]] += value
        category_of[row["asset_symbol"]] = row["asset_category"]
        by_category[row["asset_category"]] += value
        by_type[row["tipo"]] += value
        total += value

    return {
        "total": total,
        "by_asset": [
            {"asset_symbol": s, "asset_category": category_of[s], "total": t}
            for s, t in sorted(by_asset.items())
        ],
        "by_category": [
            {"asset_category": c, "total": t} for c, t in sorted(by_category.items())
        ],
        "by_type": dict(by_type),
    }


# --------------------------------------------------------------------------- #
# Estimativa de IR — renda variavel (STORY-02-11)
# --------------------------------------------------------------------------- #
# Aliquotas de IR sobre ganho de capital por categoria de RV (estimativa).
# Cripto e tratada separadamente (STORY-02-12); RF/Tesouro usam tabela regressiva.
_IR_ALIQUOTAS: dict[str, float] = {
    "Ações Nacionais": 0.15,
    "ETFs": 0.15,
    "FIIs": 0.20,
}


async def estimate_ir(conn: asyncpg.Connection, user_id: str) -> dict[str, Any]:
    """Estimativa de IR por categoria de RV: max(0, ganho) * aliquota.

    So considera posicoes com preco conhecido (valor_atual). Categorias fora do
    mapa de aliquotas (RF, Aposentadoria, Cripto) nao entram nesta estimativa.
    """
    positions = await calculate_positions(conn, user_id)

    valor_by_cat: dict[str, float] = defaultdict(float)
    custo_by_cat: dict[str, float] = defaultdict(float)
    for pos in positions:
        cat = pos["asset_category"]
        if cat in _IR_ALIQUOTAS and pos["valor_atual"] is not None:
            valor_by_cat[cat] += float(pos["valor_atual"])
            custo_by_cat[cat] += float(pos["custo_total"])

    categories: list[dict[str, Any]] = []
    total_ir = 0.0
    for cat in sorted(valor_by_cat):
        valor_atual = valor_by_cat[cat]
        custo_total = custo_by_cat[cat]
        ganho = valor_atual - custo_total
        aliquota = _IR_ALIQUOTAS[cat]
        ir_estimado = max(0.0, ganho) * aliquota
        total_ir += ir_estimado
        categories.append(
            {
                "category": cat,
                "valor_atual": valor_atual,
                "custo_total": custo_total,
                "ganho": ganho,
                "aliquota": aliquota,
                "ir_estimado": ir_estimado,
            }
        )
    return {"total_ir": total_ir, "categories": categories}


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
