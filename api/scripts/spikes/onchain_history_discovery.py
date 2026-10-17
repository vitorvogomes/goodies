#!/usr/bin/env python3
"""Discovery READ-ONLY do histórico on-chain EVM (Rabby) — Tier 2 on-chain (passo 1).

Diferente do Binance (custo explícito em USDT/trade), on-chain só há TRANSFERÊNCIAS. Para
inferir CUSTO, correlacionamos por tx hash: stablecoin/ETH que SAIU + ativo que ENTROU no
mesmo tx = swap com preço inferível. Este script mostra, por ativo detido, os eventos de
ENTRADA e se há um OUT correlacionado (swap) — pra julgar a viabilidade da reconstrução.

Não grava nada; não imprime endereço (só símbolos/quantias/datas e hash encurtado).

Uso:
    DATABASE_URL=postgresql://goodies:goodies@127.0.0.1:5432/goodies \
        uv run python -m scripts.spikes.onchain_history_discovery
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings

_V2 = "https://api.etherscan.io/v2/api"
# (rótulo da chain, chainid) — Rabby roda em Ethereum + Arbitrum
_CHAINS = [("ethereum", 1), ("arbitrum", 42161)]
_STABLES = {"USDC", "USDT", "DAI", "USDC.E", "USDBC"}


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()


async def _get(client: httpx.AsyncClient, chainid: int, action: str, addr: str) -> list[dict]:
    r = await client.get(
        _V2,
        params={
            "chainid": chainid, "module": "account", "action": action,
            "address": addr, "page": 1, "offset": 1000, "sort": "asc",
            "apikey": settings.etherscan_api_key,
        },
        timeout=25.0,
    )
    r.raise_for_status()
    data = r.json()
    res = data.get("result")
    return res if isinstance(res, list) else []


def _amount(t: dict) -> float:
    try:
        return float(t["value"]) / (10 ** int(t.get("tokenDecimal", 18)))
    except Exception:
        return 0.0


async def _scan_chain(client: httpx.AsyncClient, chain: str, chainid: int, addr: str) -> None:
    addr_l = addr.lower()
    toks = await _get(client, chainid, "tokentx", addr)
    # agrupa transfers ERC-20 por hash p/ detectar swaps (OUT stable + IN ativo no mesmo tx)
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for t in toks:
        by_hash[t["hash"]].append(t)

    in_by_sym: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"qty": 0.0, "n": 0, "swap_n": 0, "stable_out": 0.0, "first": None, "last": None}
    )
    for _h, group in by_hash.items():
        stable_out = sum(
            _amount(t) for t in group
            if t["from"].lower() == addr_l and t.get("tokenSymbol", "").upper() in _STABLES
        )
        for t in group:
            if t["to"].lower() != addr_l:
                continue
            sym = t.get("tokenSymbol", "?")
            if sym.upper() in _STABLES:
                continue  # entrada de stable = aporte de caixa, não ativo de risco
            d = in_by_sym[sym]
            d["qty"] += _amount(t)
            d["n"] += 1
            day = _day(int(t["timeStamp"]))
            d["first"] = day if d["first"] is None else min(d["first"], day)
            d["last"] = day if d["last"] is None else max(d["last"], day)
            if stable_out > 0:
                d["swap_n"] += 1
                d["stable_out"] += stable_out

    # ETH nativo (txlist): entradas de valor > 0
    native = await _get(client, chainid, "txlist", addr)
    eth_in = sum(
        float(t["value"]) / 1e18 for t in native
        if t.get("to", "").lower() == addr_l and t.get("isError") == "0"
    )
    eth_in_n = sum(
        1 for t in native
        if t.get("to", "").lower() == addr_l and float(t.get("value", 0)) > 0
    )

    print(f"\n### {chain} (chainid {chainid})")
    print(f"ERC-20 transfers: {len(toks)} | txs nativas: {len(native)}")
    print(f"ETH nativo recebido: {eth_in:.6f} em {eth_in_n} entradas (sem custo "
          f"correlacionado — precisa de internal txs / DEX)")
    if not in_by_sym:
        print("  (nenhuma entrada de token ERC-20 de risco)")
    for sym, d in sorted(in_by_sym.items(), key=lambda x: -x[1]["qty"]):
        swap = (f"{d['swap_n']} via swap (~{d['stable_out']:.2f} stable saíram)"
                if d["swap_n"] else "0 swaps detectados (transfer/airdrop?)")
        print(f"  {sym}: entrou {d['qty']:.6f} em {d['n']} eventos [{swap}] "
              f"| {d['first']}..{d['last']}")


async def _main() -> None:
    addr = settings.wallet_rabby_address
    if not addr or not settings.etherscan_api_key:
        print("[erro] WALLET_RABBY_ADDRESS / ETHERSCAN_API_KEY ausentes")
        return
    print("=" * 74)
    print("DISCOVERY ON-CHAIN EVM (Rabby) — viabilidade de custo por swap")
    print("=" * 74)
    async with httpx.AsyncClient() as client:
        for chain, chainid in _CHAINS:
            try:
                await _scan_chain(client, chain, chainid, addr)
            except Exception as exc:
                print(f"\n### {chain}: falhou ({exc})")
    print("\n" + "=" * 74)
    print("Leitura: 'via swap' = dá p/ inferir custo (stable saiu no mesmo tx). "
          "'transfer/airdrop' e ETH nativo = custo não direto (origem em outra carteira/bridge).")
    print("=" * 74)


if __name__ == "__main__":
    asyncio.run(_main())
