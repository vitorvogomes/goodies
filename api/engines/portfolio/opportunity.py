"""Oportunidade de mercado nos aportes (v2.2 — F5): quanto o preço de cada ativo caiu ou subiu, para
o aporte do mês pender um pouco para o que está em baixa e um pouco menos para o que está nas
máximas. Três sinais, todos em % (negativo = em baixa):

- `var_3m`: o preço de hoje × o de 90 dias atrás;
- `vs_pm`: o preço de hoje × o seu preço médio de compra (cripto não tem custo por ativo: fica de
  fora);
- `dd_52w`: o preço de hoje × a máxima das últimas 52 semanas (≤ 0).

O fator é limitado: `1 + 0,25 · s`, com `s = −(média ponderada dos sinais) ÷ 30%`, preso em [−1, 1]
— entre 0,75× e 1,25× do peso do ativo na divisão da classe. Sinal sem dado sai da média (os pesos
são renormalizados); sem nenhum, o fator é 1 (neutro). A divisão entre as classes não muda.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import asyncpg

WEIGHTS = {"var_3m": Decimal("0.4"), "vs_pm": Decimal("0.3"), "dd_52w": Decimal("0.3")}
SCALE = Decimal(30)  # um sinal médio de −30% leva ao limite
TILT = Decimal("0.25")  # o fator fica entre 0,75 e 1,25
_PCT = Decimal("0.01")
_FACTOR = Decimal("0.0001")


@dataclass(frozen=True)
class Signals:
    var_3m: Decimal | None = None
    vs_pm: Decimal | None = None
    dd_52w: Decimal | None = None


def pct_change(now: Decimal | None, ref: Decimal | None) -> Decimal | None:
    if now is None or ref is None or ref <= 0:
        return None
    return ((now / ref - 1) * 100).quantize(_PCT)


def factor(s: Signals) -> Decimal:
    """O peso do ativo na divisão da classe: entre 0,75 (nas máximas) e 1,25 (em baixa)."""
    have = {k: getattr(s, k) for k in WEIGHTS if getattr(s, k) is not None}
    if not have:
        return Decimal(1)
    total_w = sum((WEIGHTS[k] for k in have), Decimal(0))
    mean = sum((WEIGHTS[k] * v for k, v in have.items()), Decimal(0)) / total_w
    score = max(Decimal(-1), min(Decimal(1), -mean / SCALE))
    return (1 + TILT * score).quantize(_FACTOR)


def signals(
    price: Decimal | None,
    price_90d: Decimal | None,
    max_52w: Decimal | None,
    avg_cost: Decimal | None,
) -> Signals:
    return Signals(
        var_3m=pct_change(price, price_90d),
        vs_pm=pct_change(price, avg_cost),
        dd_52w=pct_change(price, max_52w) if max_52w is not None else None,
    )


def reference_day(month: date, today: date) -> date:
    """O dia dos sinais de um mês: o 1º dia dele (ou hoje, se ainda não chegou). Fixo no mês, a
    divisão (e a lista de compras) não muda a cada dia de mercado, e um mês passado não é refeito
    com o mercado de hoje."""
    return min(month.replace(day=1), today)


async def market_signals(
    conn: asyncpg.Connection, owner: str, tickers: list[str], today: date
) -> dict[str, Signals]:
    """Os sinais de cada ticker em `today` (o dia de referência) pelo histórico de preço
    (`asset_price_history`: o último preço até o dia) e pelo preço médio das compras até ele
    (`asset_operations`). Ticker sem preço até o dia não entra."""
    if not tickers:
        return {}
    rows = await conn.fetch(
        """
        SELECT t.ticker,
          coalesce(
            (SELECT price_brl FROM asset_price_history h WHERE h.ticker = t.ticker
               AND h.ref_date <= $5 ORDER BY h.ref_date DESC LIMIT 1),
            (SELECT price_brl FROM asset_prices p WHERE p.ticker = t.ticker
               AND (p.fetched_at AT TIME ZONE 'America/Sao_Paulo')::date <= $5)
          ) AS price,
          (SELECT price_brl FROM asset_price_history h WHERE h.ticker = t.ticker
             AND h.ref_date <= $2 ORDER BY h.ref_date DESC LIMIT 1) AS price_90d,
          (SELECT min(ref_date) FROM asset_price_history h WHERE h.ticker = t.ticker) AS first_day,
          (SELECT max(price_brl) FROM asset_price_history h WHERE h.ticker = t.ticker
             AND h.ref_date > $3 AND h.ref_date <= $5) AS max_52w,
          (SELECT sum(quantidade * valor_unitario) / nullif(sum(quantidade), 0)
             FROM asset_operations o WHERE o.user_id = $4 AND o.asset_symbol = t.ticker
             AND o.tipo IN ('compra', 'aporte') AND o.data_operacao <= $5) AS avg_cost
        FROM unnest($1::text[]) AS t(ticker)
        """,
        tickers,
        today - timedelta(days=90),
        today - timedelta(days=365),
        owner,
        today,
    )
    out: dict[str, Signals] = {}
    for r in rows:
        if r["price"] is None:
            continue
        price = Decimal(r["price"])
        # sem histórico que cubra 90 dias, a variação de 3 meses não existe (não o 1º dia visto)
        p90 = Decimal(r["price_90d"]) if r["price_90d"] is not None else None
        top = Decimal(r["max_52w"]) if r["max_52w"] is not None else None
        # a máxima de 52 semanas só vale com pelo menos 6 meses de histórico
        if r["first_day"] is None or r["first_day"] > today - timedelta(days=180):
            top = None
        else:
            top = max(top, price) if top is not None else None
        cost = Decimal(r["avg_cost"]) if r["avg_cost"] is not None else None
        out[r["ticker"]] = signals(price, p90, top, cost)
    return out
