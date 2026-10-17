#!/usr/bin/env python3
"""Spike READ-ONLY: mede quanto do HISTÓRICO cripto por ativo é recuperável (Tier 2).

Não grava NADA e não imprime endereço/chave (redige `note`s). Para cada fonte de custódia
dos ativos atualmente detidos (wallet_positions + defi_positions), sonda o endpoint de
HISTÓRICO que hoje NÃO usamos e reporta contagem/período + um veredito de recuperabilidade
do PREÇO MÉDIO por ativo:

- **yes**     — CEX com fiat+trade history (Binance): custo em BRL/USDT derivável.
- **partial** — só on-chain (transfers/fills): quantidades+datas, mas custo BRL exige preço
                histórico (CoinGecko) + swaps cripto↔cripto (impreciso).
- **no**      — sem fonte de histórico (HyperEVM sem indexer; KuCoin sem API — lacuna
                permanente, conta zerada).

Uso (sandbox off, DATABASE_URL local; lê credenciais/endereços de `settings`):
    DATABASE_URL=postgresql://goodies:goodies@127.0.0.1:5432/goodies \
        uv run python -m scripts.spikes.crypto_history_spike [--user <id|email>]

Decisão de avançar para o Tier 2 (reconstrução por ativo) fica para o Vitor após o relatório.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from config import settings
from db.connection import close_pool, get_pool, init_pool
from scripts._common import resolve_owner, user_arg

# --------------------------------------------------------------------------- #
# Núcleo puro (testado): veredito + redação de segredos
# --------------------------------------------------------------------------- #


@dataclass
class Probe:
    """Resultado redigido de uma sonda de histórico (só contagem/período, sem segredo)."""

    source: str
    endpoint: str
    ok: bool
    count: int = 0
    date_min: str | None = None
    date_max: str | None = None
    note: str = ""


# Custódia → base de recuperabilidade do custo POR ATIVO.
_CEX = {"binance"}  # fiat+trade history → custo BRL/USDT derivável
_ONCHAIN = {"ethereum", "arbitrum", "solana", "liquid", "bitcoin", "hyperliquid", "defi"}
# sem fonte de histórico: HyperEVM (RPC sem txlist) e qualquer custódia desconhecida (KuCoin)


def base_verdict(custody: str) -> str:
    """Veredito-base só pela custódia (antes de saber se a sonda achou eventos)."""
    c = custody.lower()
    if c in _CEX:
        return "yes"
    if c in _ONCHAIN:
        return "partial"
    return "no"


def recoverability(base: str, probe: Probe | None) -> str:
    """Refina o veredito-base pelo que a sonda achou: sem fonte/sem eventos → 'no'."""
    if base == "no":
        return "no"
    if probe is None or not probe.ok or probe.count == 0:
        return "no"
    return base


_SECRET_RES = [
    re.compile(r"0x[0-9a-fA-F]{40,}"),  # endereço/contrato EVM
    re.compile(r"\b[0-9a-fA-F]{64}\b"),  # api key / asset id / chave 64-hex
    re.compile(r"\b(?:bc1|tb1)[a-z0-9]{20,}\b"),  # bech32 Bitcoin
    re.compile(r"\b(?:lq1|ex1|VJL|VT|Az)[A-Za-z0-9]{24,}\b"),  # endereços Liquid
]


def redact(text: str) -> str:
    """Remove qualquer endereço/chave de um texto livre (defesa do relatório)."""
    out = text
    for rx in _SECRET_RES:
        out = rx.sub("[redacted]", out)
    return out


def _asset_source_key(custody: str, protocol: str | None) -> str | None:
    c = custody.lower()
    table = {
        "binance": "binance-trades",
        "ethereum": "evm-eth",
        "arbitrum": "evm-arb",
        "solana": "solana",
        "bitcoin": "esplora-btc",
        "liquid": "esplora-liquid",
        "hyperliquid": "hyperliquid",
        "hyperevm": None,  # sem indexer de histórico
    }
    if c in table:
        return table[c]
    if c == "defi":
        return "evm-arb" if "pendle" in (protocol or "").lower() else "solana"
    return None


def render_report(
    held: list[dict[str, Any]], probes: dict[str, Probe]
) -> str:
    """Tabela markdown (ativos + veredito) + resumo por fonte. Redige toda `note`."""
    lines: list[str] = []
    lines.append("# Spike de histórico cripto (Tier 2 feasibility)\n")
    lines.append("## Recuperabilidade por ativo detido\n")
    lines.append("| Ativo | Custódia | Fonte de histórico | Eventos | Período | Recuperável |")
    lines.append("|---|---|---|---:|---|---|")
    for h in sorted(held, key=lambda x: (x["custody"], x["asset"])):
        key = _asset_source_key(h["custody"], h.get("protocol"))
        probe = probes.get(key) if key else None
        verdict = recoverability(base_verdict(h["custody"]), probe)
        n = probe.count if probe else 0
        period = (
            f"{probe.date_min}..{probe.date_max}"
            if probe and probe.date_min
            else "—"
        )
        lines.append(
            f"| {h['asset']} | {h['custody']} | {key or '—'} | {n} | {period} | "
            f"**{verdict}** |"
        )
    lines.append("\n## Resumo por fonte (sondas)\n")
    lines.append("| Fonte | Endpoint | OK | Eventos | Período | Nota |")
    lines.append("|---|---|---|---:|---|---|")
    for src, p in sorted(probes.items()):
        period = f"{p.date_min}..{p.date_max}" if p.date_min else "—"
        lines.append(
            f"| {src} | {p.endpoint} | {'sim' if p.ok else 'não'} | {p.count} | "
            f"{period} | {redact(p.note)} |"
        )
    lines.append(
        "\n> **KuCoin:** lacuna permanente — sem API configurada e conta zerada "
        "(ativos repassados a wallets/Binance). Histórico irrecuperável.\n"
        "> **partial** = quantidade+data on-chain existem, mas o custo BRL exige preço "
        "histórico + decodificação de swaps (aproximado)."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Sondas de rede (best-effort, fail-soft; nunca levantam)
# --------------------------------------------------------------------------- #


def _date_range(epochs_s: list[float]) -> tuple[str | None, str | None]:
    if not epochs_s:
        return None, None
    fmt = lambda e: datetime.fromtimestamp(e, tz=UTC).date().isoformat()  # noqa: E731
    return fmt(min(epochs_s)), fmt(max(epochs_s))


def _sign(secret: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return {**params, "signature": sig}


async def _binance_offset(client: httpx.AsyncClient) -> int:
    """serverTime - relógio local (ms). Corrige clock-skew (WSL) — sem isso a Binance 400."""
    try:
        r = await client.get("https://api.binance.com/api/v3/time", timeout=10.0)
        r.raise_for_status()
        return int(r.json()["serverTime"]) - int(datetime.now(tz=UTC).timestamp() * 1000)
    except Exception:
        return 0


async def _binance_signed(
    client: httpx.AsyncClient, path: str, extra: dict, offset: int = 0
) -> Any:
    ts = int(datetime.now(tz=UTC).timestamp() * 1000) + offset
    params = _sign(settings.binance_api_secret, {"timestamp": ts, "recvWindow": 5000, **extra})
    resp = await client.get(
        f"https://api.binance.com{path}",
        params=params,
        headers={"X-MBX-APIKEY": settings.binance_api_key},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


async def _probe_binance(client: httpx.AsyncClient) -> dict[str, Probe]:
    out: dict[str, Probe] = {}
    if not settings.binance_api_key or not settings.binance_api_secret:
        return {
            "binance-trades": Probe("binance-trades", "myTrades", False, note="sem credencial")
        }
    off = await _binance_offset(client)  # corrige skew antes das chamadas assinadas
    # fiat orders (compras BRL via cartão/pix): transactionType=0 (buy)
    try:
        d = await _binance_signed(client, "/sapi/v1/fiat/orders", {"transactionType": 0}, off)
        rows = d.get("data", []) if isinstance(d, dict) else []
        mn, mx = _date_range([int(r.get("createTime", 0)) / 1000 for r in rows])
        out["binance-fiat"] = Probe(
            "binance-fiat", "/sapi/v1/fiat/orders", True, len(rows), mn, mx,
            "compras fiat (BRL) — custo direto",
        )
    except Exception as exc:
        out["binance-fiat"] = Probe("binance-fiat", "/sapi/v1/fiat/orders", False, note=str(exc))
    # deposit history (cripto recebida)
    try:
        rows = await _binance_signed(client, "/sapi/v1/capital/deposit/hisrec", {}, off)
        rows = rows if isinstance(rows, list) else []
        mn, mx = _date_range([int(r.get("insertTime", 0)) / 1000 for r in rows])
        out["binance-deposit"] = Probe(
            "binance-deposit", "/sapi/v1/capital/deposit/hisrec", True, len(rows), mn, mx
        )
    except Exception as exc:
        out["binance-deposit"] = Probe(
            "binance-deposit", "/sapi/v1/capital/deposit/hisrec", False, note=str(exc)
        )
    # myTrades (representativo: BTCUSDT) — confirma se o trade history responde
    try:
        rows = await _binance_signed(client, "/api/v3/myTrades", {"symbol": "BTCUSDT"}, off)
        rows = rows if isinstance(rows, list) else []
        mn, mx = _date_range([int(r.get("time", 0)) / 1000 for r in rows])
        out["binance-trades"] = Probe(
            "binance-trades", "/api/v3/myTrades?symbol=…", True, len(rows), mn, mx,
            "trade history por par (iterar símbolos)",
        )
    except Exception as exc:
        out["binance-trades"] = Probe(
            "binance-trades", "/api/v3/myTrades", False, note=str(exc)
        )
    return out


async def _probe_etherscan(client: httpx.AsyncClient, chainid: int, key: str) -> Probe:
    addr = settings.wallet_rabby_address
    if not addr or not settings.etherscan_api_key:
        return Probe(key, "txlist", False, note="sem endereço/chave")
    try:
        resp = await client.get(
            "https://api.etherscan.io/v2/api",
            params={
                "chainid": chainid, "module": "account", "action": "tokentx",
                "address": addr, "page": 1, "offset": 100, "sort": "asc",
                "apikey": settings.etherscan_api_key,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("result", []) if isinstance(data.get("result"), list) else []
        mn, mx = _date_range([int(r.get("timeStamp", 0)) for r in rows])
        return Probe(key, "account&action=tokentx", True, len(rows), mn, mx,
                     "transfers ERC-20 (sem custo BRL)")
    except Exception as exc:
        return Probe(key, "tokentx", False, note=str(exc))


async def _probe_solana(client: httpx.AsyncClient) -> Probe:
    addr = settings.wallet_phantom_sol_address
    if not addr:
        return Probe("solana", "getSignaturesForAddress", False, note="sem endereço")
    try:
        resp = await client.post(
            settings.solana_rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
                  "params": [addr, {"limit": 1000}]},
            timeout=15.0,
        )
        resp.raise_for_status()
        rows = resp.json().get("result", []) or []
        mn, mx = _date_range([int(r["blockTime"]) for r in rows if r.get("blockTime")])
        return Probe("solana", "getSignaturesForAddress", True, len(rows), mn, mx,
                     "assinaturas (decodificar p/ swaps)")
    except Exception as exc:
        return Probe("solana", "getSignaturesForAddress", False, note=str(exc))


async def _probe_esplora(client: httpx.AsyncClient, base: str, addr: str, key: str) -> Probe:
    if not addr:
        return Probe(key, "/address/:addr/txs", False, note="endereço manual/confidencial")
    try:
        resp = await client.get(f"{base.rstrip('/')}/address/{addr}/txs", timeout=15.0)
        resp.raise_for_status()
        rows = resp.json() or []
        mn, mx = _date_range(
            [int(r["status"]["block_time"]) for r in rows
             if r.get("status", {}).get("block_time")]
        )
        return Probe(key, "/address/:addr/txs", True, len(rows), mn, mx,
                     "txs on-chain (sem custo BRL)")
    except Exception as exc:
        return Probe(key, "/address/:addr/txs", False, note=str(exc))


async def _probe_hyperliquid(client: httpx.AsyncClient) -> Probe:
    addr = settings.wallet_rabby_address
    if not addr:
        return Probe("hyperliquid", "userFills", False, note="sem endereço")
    try:
        resp = await client.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "userFills", "user": addr}, timeout=15.0,
        )
        resp.raise_for_status()
        rows = resp.json() or []
        mn, mx = _date_range([int(r.get("time", 0)) / 1000 for r in rows])
        return Probe("hyperliquid", "info type=userFills", True, len(rows), mn, mx,
                     "fills (preço em USDC)")
    except Exception as exc:
        return Probe("hyperliquid", "userFills", False, note=str(exc))


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #


async def _held_assets(conn: Any, uid: str) -> list[dict[str, Any]]:
    wallets = await conn.fetch(
        "SELECT DISTINCT chain, asset_symbol FROM wallet_positions WHERE user_id = $1",
        uid,
    )
    defi = await conn.fetch(
        "SELECT protocol, asset_symbol FROM defi_positions WHERE user_id = $1 AND is_active",
        uid,
    )
    held = [{"asset": r["asset_symbol"], "custody": r["chain"], "protocol": None} for r in wallets]
    held += [
        {"asset": r["asset_symbol"], "custody": "defi", "protocol": r["protocol"]} for r in defi
    ]
    return held


async def _run_probes() -> dict[str, Probe]:
    probes: dict[str, Probe] = {}
    # client genérico (Binance/Etherscan/Solana/Hyperliquid)
    async with httpx.AsyncClient() as client:
        probes.update(await _probe_binance(client))
        probes["evm-eth"] = await _probe_etherscan(client, 1, "evm-eth")
        probes["evm-arb"] = await _probe_etherscan(client, 42161, "evm-arb")
        probes["solana"] = await _probe_solana(client)
        probes["hyperliquid"] = await _probe_hyperliquid(client)
    # ADR-005: Bitcoin e Liquid em CLIENTS SEPARADOS (bases distintas)
    async with httpx.AsyncClient() as btc:
        probes["esplora-btc"] = await _probe_esplora(
            btc, settings.btc_base_url, settings.wallet_trust_btc_address, "esplora-btc"
        )
    async with httpx.AsyncClient() as lq:
        probes["esplora-liquid"] = await _probe_esplora(
            lq, settings.liquid_base_url, settings.wallet_sideswap_address, "esplora-liquid"
        )
    return probes


async def _main() -> None:
    await init_pool(settings.database_url)
    pool = get_pool()
    async with pool.acquire() as conn:
        owner = await resolve_owner(conn, user_arg())
        if not owner:
            print("[erro] Nenhum usuário no banco.")
            sys.exit(1)
        held = await _held_assets(conn, str(owner["id"]))
    probes = await _run_probes()
    await close_pool()
    print(render_report(held, probes))


if __name__ == "__main__":
    asyncio.run(_main())
