#!/usr/bin/env python3
"""Discovery READ-ONLY do histórico Binance (Tier 2, passo 1).

Não grava NADA e não imprime segredo. Puxa o histórico que hoje NÃO usamos (myTrades por
par, fiat orders BRL, depósitos/saques) e cruza com:
- o saldo ATUAL escaneado (wallet_positions chain=binance) → a reconstrução fecha? (net das
  ops ≈ saldo atual);
- o aporte do ledger (categoria 'Binance') → âncora de BRL;
- a viabilidade do câmbio histórico USDT/BRL (CoinGecko /coins/tether/history) p/ converter o
  custo dos trades cotados em USDT → BRL.

Uso (sandbox off, DATABASE_URL local; lê credenciais de `settings`):
    DATABASE_URL=postgresql://goodies:goodies@127.0.0.1:5432/goodies \
        uv run python -m scripts.spikes.binance_history_discovery [--user <id|email>]
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from config import settings
from db.connection import close_pool, get_pool, init_pool
from scripts._common import resolve_owner, user_arg

_BASE = "https://api.binance.com"
# pares a investigar = ativos cripto detidos na Binance cotados em USDT
_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
_WINDOW_DAYS = 90  # fiat/deposit/withdraw são limitados a janelas de ~90 dias


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


async def _signed(client: httpx.AsyncClient, path: str, extra: dict, off: int) -> Any:
    params = _sign(
        settings.binance_api_secret,
        {"timestamp": _ms(datetime.now(tz=UTC)) + off, "recvWindow": 5000, **extra},
    )
    r = await client.get(
        f"{_BASE}{path}", params=params,
        headers={"X-MBX-APIKEY": settings.binance_api_key}, timeout=20.0,
    )
    r.raise_for_status()
    return r.json()


def _windows(start: datetime, end: datetime) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=_WINDOW_DAYS), end)
        out.append((_ms(cur), _ms(nxt)))
        cur = nxt
    return out


async def _trades(client: httpx.AsyncClient, symbol: str, off: int) -> list[dict]:
    rows = await _signed(client, "/api/v3/myTrades", {"symbol": symbol, "limit": 1000}, off)
    return rows if isinstance(rows, list) else []


async def _fiat(client: httpx.AsyncClient, off: int, start: datetime, end: datetime) -> list[dict]:
    out: list[dict] = []
    for b, e in _windows(start, end):
        try:
            d = await _signed(
                client, "/sapi/v1/fiat/orders",
                {"transactionType": 0, "beginTime": b, "endTime": e, "rows": 500}, off,
            )
            out.extend(d.get("data", []) if isinstance(d, dict) else [])
        except Exception:
            continue
    return [r for r in out if str(r.get("status")) in ("Successful", "Completed")]


async def _capital(
    client: httpx.AsyncClient, path: str, off: int, start: datetime, end: datetime
) -> list[dict]:
    out: list[dict] = []
    for b, e in _windows(start, end):
        try:
            rows = await _signed(client, path, {"startTime": b, "endTime": e}, off)
            out.extend(rows if isinstance(rows, list) else [])
        except Exception:
            continue
    return out


async def _usdt_brl_on(client: httpx.AsyncClient, day_iso: str) -> float | None:
    """Câmbio USDT→BRL histórico (CoinGecko) p/ uma data — viabilidade do custo em BRL."""
    d = datetime.fromisoformat(day_iso).strftime("%d-%m-%Y")
    try:
        params: dict[str, Any] = {"date": d, "localization": "false"}
        if settings.coingecko_api_key:
            params["x_cg_demo_api_key"] = settings.coingecko_api_key
        r = await client.get(
            "https://api.coingecko.com/api/v3/coins/tether/history", params=params, timeout=20.0
        )
        r.raise_for_status()
        return float(r.json()["market_data"]["current_price"]["brl"])
    except Exception:
        return None


async def _scanned_binance(conn: Any, uid: str) -> dict[str, float]:
    rows = await conn.fetch(
        "SELECT asset_symbol, sum(quantity) q FROM wallet_positions "
        "WHERE user_id=$1 AND chain='binance' GROUP BY asset_symbol",
        uid,
    )
    return {r["asset_symbol"]: float(r["q"]) for r in rows}


async def _ledger_binance(conn: Any) -> float:
    v = await conn.fetchval(
        "SELECT COALESCE(sum(amount),0) FROM transactions WHERE category='Binance'"
    )
    return float(v)


async def _main() -> None:
    await init_pool(settings.database_url)
    pool = get_pool()
    async with pool.acquire() as conn:
        owner = await resolve_owner(conn, user_arg())
        if not owner:
            print("[erro] sem usuário")
            sys.exit(1)
        scanned = await _scanned_binance(conn, str(owner["id"]))
        ledger = await _ledger_binance(conn)
    await close_pool()

    if not settings.binance_api_key or not settings.binance_api_secret:
        print("[erro] sem credencial Binance")
        return

    start = datetime(2024, 6, 1, tzinfo=UTC)
    end = datetime.now(tz=UTC)
    async with httpx.AsyncClient() as client:
        off = await _offset(client)
        per_symbol = {s: await _trades(client, s, off) for s in _PAIRS}
        fiat = await _fiat(client, off, start, end)
        deposits = await _capital(client, "/sapi/v1/capital/deposit/hisrec", off, start, end)
        withdraws = await _capital(client, "/sapi/v1/capital/withdraw/hisrec", off, start, end)
        # viabilidade FX: pega a data do 1º trade e busca o USDT/BRL histórico
        sample_day = None
        for rows in per_symbol.values():
            if rows:
                sample_day = _day(int(rows[0]["time"]))
                break
        fx = await _usdt_brl_on(client, sample_day) if sample_day else None

    print("=" * 72)
    print("DISCOVERY BINANCE — Tier 2 (read-only)")
    print("=" * 72)
    print(f"\nAporte ledger (categoria 'Binance'): R$ {ledger:,.2f}")
    print(f"Fiat orders (depósitos BRL na Binance): {len(fiat)}")
    if fiat:
        tot = sum(float(r.get("amount", 0) or 0) for r in fiat)
        moedas = {str(r.get("fiatCurrency")) for r in fiat}
        print(f"  total fiat: {tot:,.2f} {sorted(moedas)} (deve casar com o aporte do ledger)")
    print(f"Depósitos cripto: {len(deposits)} | Saques: {len(withdraws)}")
    for d in deposits:
        print(f"  +dep {d.get('amount')} {d.get('coin')} em {_day(int(d.get('insertTime',0)))}")
    for w in withdraws:
        ts = int(w.get("completeTime") or w.get("applyTime") or 0)
        print(f"  -saq {w.get('amount')} {w.get('coin')} em {_day(ts) if ts else '?'}")

    print("\n--- por par (myTrades) ---")
    base_net: dict[str, float] = defaultdict(float)
    usdt_net = 0.0
    for sym, rows in per_symbol.items():
        base = sym.replace("USDT", "")
        buys = [t for t in rows if t.get("isBuyer")]
        sells = [t for t in rows if not t.get("isBuyer")]
        qty_buy = sum(float(t["qty"]) for t in buys)
        qty_sell = sum(float(t["qty"]) for t in sells)
        usdt_buy = sum(float(t["quoteQty"]) for t in buys)
        usdt_sell = sum(float(t["quoteQty"]) for t in sells)
        base_net[base] += qty_buy - qty_sell
        usdt_net += usdt_sell - usdt_buy  # USDT que entrou(+)/saiu(-) por trades
        dates = sorted(_day(int(t["time"])) for t in rows)
        avg = usdt_buy / qty_buy if qty_buy else 0.0
        period = f"{dates[0]}..{dates[-1]}" if dates else "-"
        print(
            f"{sym}: {len(rows)} trades ({len(buys)}c/{len(sells)}v) | "
            f"comprou {qty_buy:.8f} por {usdt_buy:.2f} USDT (médio {avg:.2f}) | "
            f"vendeu {qty_sell:.8f} por {usdt_sell:.2f} USDT | "
            f"net {qty_buy - qty_sell:.8f} {base} | {period}"
        )

    print("\n--- reconciliação prévia: net das ops vs saldo escaneado ---")
    for base in sorted(set(base_net) | set(scanned) - {"USDT"}):
        net = base_net.get(base, 0.0)
        scan = scanned.get(base, 0.0)
        flag = "OK" if abs(net - scan) < 1e-6 else "DIVERGE"
        print(f"  {base}: ops_net {net:.8f} | escaneado {scan:.8f} | Δ {net - scan:+.8f}  [{flag}]")
    print(f"  USDT escaneado: {scanned.get('USDT', 0.0):.8f} (resto de caixa)")

    print("\n--- viabilidade câmbio histórico (custo em BRL) ---")
    if fx and sample_day:
        print(f"  CoinGecko USDT/BRL em {sample_day} = R$ {fx:.4f} → OK (1 call por data de trade)")
    else:
        print("  CoinGecko historical indisponível (checar plano/limite)")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(_main())
