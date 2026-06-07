#!/usr/bin/env python3
"""Reconstrução de custo por ativo do Binance (Tier 2, pragmático) — READ-ONLY (passo 2).

Custo em BRL dos trades via câmbio histórico do par Binance `USDTBRL` (klines diárias).
Modelo escolhido (Vitor): só trades; a quantidade excedente (escaneado - net negociado =
depósitos/Earn/convert) entra a CUSTO ZERO. Preço médio negociado = Σ(custo compras BRL)/
Σ(qty compras); custo do detido = preço médio x net_negociado (gap a zero).

Não grava nada, não imprime segredo. Apenas mostra os números p/ validar antes de persistir.

Uso:
    DATABASE_URL=postgresql://goodies:goodies@127.0.0.1:5432/goodies \
        uv run python ../scripts/binance_history_discovery.py   # 1º (panorama)
    DATABASE_URL=...  uv run python ../scripts/reconstruct_binance_cost.py [--user <id|email>]
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

import httpx
from _common import resolve_owner, user_arg

from config import settings
from db.connection import close_pool, get_pool, init_pool

_BASE = "https://api.binance.com"
_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date().isoformat()


def _sign(secret: str, params: dict[str, Any]) -> dict[str, Any]:
    sig = hmac.new(secret.encode(), urlencode(params).encode(), hashlib.sha256).hexdigest()
    return {**params, "signature": sig}


async def _offset(client: httpx.AsyncClient) -> int:
    try:
        r = await client.get(f"{_BASE}/api/v3/time", timeout=10.0)
        r.raise_for_status()
        return int(r.json()["serverTime"]) - _ms(datetime.now(tz=UTC))
    except Exception:
        return 0


async def _trades(client: httpx.AsyncClient, symbol: str, off: int) -> list[dict]:
    params = _sign(
        settings.binance_api_secret,
        {"timestamp": _ms(datetime.now(tz=UTC)) + off, "recvWindow": 5000,
         "symbol": symbol, "limit": 1000},
    )
    r = await client.get(
        f"{_BASE}/api/v3/myTrades", params=params,
        headers={"X-MBX-APIKEY": settings.binance_api_key}, timeout=20.0,
    )
    r.raise_for_status()
    rows = r.json()
    return rows if isinstance(rows, list) else []


async def _usdtbrl_by_day(client: httpx.AsyncClient, start_ms: int) -> dict[str, float]:
    """{data: close USDT/BRL} do par Binance USDTBRL (diário) a partir de start_ms."""
    out: dict[str, float] = {}
    cur = start_ms
    end = _ms(datetime.now(tz=UTC))
    while cur < end:
        r = await client.get(
            f"{_BASE}/api/v3/klines",
            params={"symbol": "USDTBRL", "interval": "1d", "startTime": cur, "limit": 1000},
            timeout=20.0,
        )
        r.raise_for_status()
        ks = r.json()
        if not ks:
            break
        for k in ks:
            out[_day(int(k[0]))] = float(k[4])  # close
        cur = int(ks[-1][0]) + 86_400_000
    return out


async def _scanned(conn: Any, uid: str) -> dict[str, float]:
    rows = await conn.fetch(
        "SELECT asset_symbol, sum(quantity) q FROM wallet_positions "
        "WHERE user_id=$1 AND chain='binance' GROUP BY asset_symbol",
        uid,
    )
    return {r["asset_symbol"]: float(r["q"]) for r in rows}


async def _current_brl(conn: Any, symbols: list[str]) -> dict[str, float]:
    rows = await conn.fetch(
        "SELECT ticker, price_brl FROM asset_prices WHERE ticker = ANY($1::text[])", symbols
    )
    return {r["ticker"]: float(r["price_brl"]) for r in rows}


def _fx(rates: dict[str, float], day: str) -> float:
    if day in rates:
        return rates[day]
    # fallback: data mais próxima anterior (fim de semana sem candle)
    earlier = [d for d in rates if d <= day]
    return rates[max(earlier)] if earlier else (next(iter(rates.values()), 0.0))


async def _main() -> None:
    await init_pool(settings.database_url)
    pool = get_pool()
    async with pool.acquire() as conn:
        owner = await resolve_owner(conn, user_arg())
        if not owner:
            print("[erro] sem usuário")
            sys.exit(1)
        scanned = await _scanned(conn, str(owner["id"]))
        current = await _current_brl(conn, ["BTC", "ETH", "SOL"])
    await close_pool()

    if not settings.binance_api_key or not settings.binance_api_secret:
        print("[erro] sem credencial Binance")
        return

    async with httpx.AsyncClient() as client:
        off = await _offset(client)
        per = {s: await _trades(client, s, off) for s in _PAIRS}
        now_ms = _ms(datetime.now(tz=UTC))
        first = min(
            (int(t["time"]) for rows in per.values() for t in rows), default=now_ms
        )
        rates = await _usdtbrl_by_day(client, first)

    print("=" * 78)
    print("RECONSTRUÇÃO DE CUSTO BINANCE (Tier 2 pragmático — trades + gap a custo zero)")
    print("=" * 78)
    tot_custo = tot_valor = 0.0
    for sym, rows in per.items():
        base = sym.replace("USDT", "")
        qty_buy = cost_buy = qty_sell = 0.0
        for t in rows:
            q, usdt = float(t["qty"]), float(t["quoteQty"])
            brl = usdt * _fx(rates, _day(int(t["time"])))
            if t.get("isBuyer"):
                qty_buy += q
                cost_buy += brl
            else:
                qty_sell += q
        dca = cost_buy / qty_buy if qty_buy else 0.0  # preço médio negociado (BRL/unid)
        net_traded = qty_buy - qty_sell
        held = scanned.get(base, 0.0)
        gap = held - net_traded
        custo_detido = dca * net_traded  # gap a custo zero
        pm_detido = custo_detido / held if held else 0.0
        price = current.get(base, 0.0)
        valor = held * price
        tot_custo += custo_detido
        tot_valor += valor
        print(f"\n{base}:")
        print(f"  negociado: comprou {qty_buy:.8f} por R$ {cost_buy:,.2f} "
              f"(preço médio R$ {dca:,.2f}) | vendeu {qty_sell:.8f}")
        print(f"  detido: {held:.8f} (net negociado {net_traded:.8f} "
              f"+ gap {gap:+.8f} a custo zero)")
        print(f"  custo do detido: R$ {custo_detido:,.2f} "
              f"| preço médio efetivo: R$ {pm_detido:,.2f}")
        print(f"  preço atual: R$ {price:,.2f} | valor atual: R$ {valor:,.2f} "
              f"| resultado: R$ {valor - custo_detido:,.2f}")
    print(f"\nTOTAL Binance: custo R$ {tot_custo:,.2f} | valor R$ {tot_valor:,.2f} "
          f"| resultado R$ {tot_valor - tot_custo:,.2f}")
    print("(o aporte do ledger 'Binance' é R$ 2.042,36; a diferença p/ o custo negociado "
          "= perdas realizadas + USDT parado)")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(_main())
