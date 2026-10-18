"""Wallet Engine — escrita de saldos escaneados (m4, STORY-04-01).

`upsert_wallet_position` é o write path do worker `wallet_scan`: grava o snapshot mais
recente do saldo por (usuário, chain, endereço, ativo). Idempotente (ON CONFLICT): uma
nova varredura atualiza quantity/source e avança `scanned_at`, sem duplicar linhas.

Leitura valorada (`list_wallet_positions`) e reconciliação (`reconcile`) alimentam os
endpoints `/api/v1/wallets/*` (consumidos pelo frontend 04-10/04-11).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from config import settings
from engines.common.assets import CRYPTO_CATEGORIES, AssetCategory
from engines.common.numbers import value_of
from engines.market import service as market_service
from engines.market.fetchers.wallets.base import WalletBalance
from engines.portfolio.service import net_quantity


class ManualPositionConflict(Exception):
    """Já existe uma posição ESCANEADA do mesmo (chain, ativo) — manual duplicaria a contagem."""


def _prefer_scanned(rows: Sequence[Any]) -> list[Any]:
    """Dedup por (chain, asset_symbol): se há linha escaneada, descarta a manual.

    Uma posição manual (`wallet_address='manual'`) e uma escaneada real coexistem como
    linhas distintas (chave única difere por endereço). Sem isto, `list`/`reconcile`
    somariam as duas (contagem dupla). A escaneada (on-chain) vence a manual.
    """
    has_scanned = {
        (r["chain"], r["asset_symbol"]) for r in rows if not r["is_manual"]
    }
    return [
        r
        for r in rows
        if not (r["is_manual"] and (r["chain"], r["asset_symbol"]) in has_scanned)
    ]


async def upsert_wallet_position(
    conn: asyncpg.Connection, user_id: str, balance: WalletBalance
) -> None:
    """Grava/atualiza o saldo escaneado (snapshot mais recente) de um ativo numa wallet."""
    await conn.execute(
        """
        INSERT INTO wallet_positions
          (user_id, chain, wallet_address, asset_symbol, quantity, source, scanned_at)
        VALUES ($1, $2, $3, $4, $5, $6, now())
        ON CONFLICT (user_id, chain, wallet_address, asset_symbol) DO UPDATE
          SET quantity = EXCLUDED.quantity,
              source = EXCLUDED.source,
              scanned_at = now()
        """,
        user_id,
        balance.chain,
        balance.wallet_address,
        balance.asset_symbol,
        balance.quantity,
        balance.source,
    )


async def upsert_manual_wallet_position(
    conn: asyncpg.Connection, user_id: str, chain: str, asset_symbol: str, quantity: float
) -> None:
    """Grava/atualiza uma posição MANUAL (ex.: Liquid confidencial, não escaneável).

    `is_manual=true`, `source='manual'`, `wallet_address='manual'` (sentinela). O sweep do
    worker nunca a remove. Valorada como qualquer outra (preço do m3 por asset_symbol).
    Rejeita (`ManualPositionConflict`) se já há linha escaneada do mesmo (chain, ativo) —
    senão as duas seriam somadas (contagem dupla).
    """
    clash = await conn.fetchval(
        "SELECT 1 FROM wallet_positions WHERE user_id = $1 AND chain = $2 "
        "AND asset_symbol = $3 AND is_manual = false LIMIT 1",
        user_id,
        chain,
        asset_symbol,
    )
    if clash:
        raise ManualPositionConflict(f"{chain}/{asset_symbol} já é escaneada")
    await conn.execute(
        """
        INSERT INTO wallet_positions
          (user_id, chain, wallet_address, asset_symbol, quantity, source, scanned_at, is_manual)
        VALUES ($1, $2, 'manual', $3, $4, 'manual', now(), true)
        ON CONFLICT (user_id, chain, wallet_address, asset_symbol) DO UPDATE
          SET quantity = EXCLUDED.quantity,
              source = 'manual',
              is_manual = true,
              scanned_at = now()
        """,
        user_id,
        chain,
        asset_symbol,
        quantity,
    )


async def delete_manual_wallet_position(
    conn: asyncpg.Connection, user_id: str, chain: str, asset_symbol: str
) -> bool:
    """Remove uma posição manual. Devolve True se removeu (False se não existia)."""
    result = await conn.execute(
        "DELETE FROM wallet_positions WHERE user_id = $1 AND chain = $2 "
        "AND asset_symbol = $3 AND is_manual = true",
        user_id,
        chain,
        asset_symbol,
    )
    return bool(result != "DELETE 0")


async def sweep_wallet_positions(
    conn: asyncpg.Connection,
    user_id: str,
    balances: list[WalletBalance],
    sources: Sequence[str] = (),
) -> int:
    """Apaga posições de um source que NÃO apareceram no scan atual (posição fechada).

    Snapshot-replace por source: o scan é a verdade para os sources que ele cobriu.
    Chamar SÓ para scan completo — um source fora (fail-soft) não deve apagar o último
    snapshot bom (outage ≠ posição fechada). Sem o sweep, um ativo vendido/zerado
    (filtrado por `qty>0` no fetcher) ficaria como posição fantasma. `sources` são as
    fontes que o fetcher declara cobrir (`SOURCES`): permitem varrer um scan completo e
    VAZIO (tudo vendido); sem elas, só os sources presentes em `balances` são varridos.
    Posições manuais (`is_manual`) NUNCA são varridas (não vêm de scan). Devolve o número
    de linhas removidas.
    """
    covered = {b.source for b in balances} | set(sources)
    if not covered:
        return 0
    sources = list(covered)
    kept = {(b.chain, b.wallet_address, b.asset_symbol) for b in balances}
    rows = await conn.fetch(
        "SELECT id, chain, wallet_address, asset_symbol FROM wallet_positions "
        "WHERE user_id = $1 AND source = ANY($2) AND is_manual = false",
        user_id,
        sources,
    )
    stale_ids = [
        r["id"]
        for r in rows
        if (r["chain"], r["wallet_address"], r["asset_symbol"]) not in kept
    ]
    if stale_ids:
        await conn.execute("DELETE FROM wallet_positions WHERE id = ANY($1)", stale_ids)
    return len(stale_ids)


async def prices_by_ticker(
    conn: asyncpg.Connection, symbols: Sequence[str]
) -> dict[str, tuple[float | None, float | None]]:
    """Preço corrente (BRL, USD) por ticker para valoração de wallet/DeFi (tudo cripto).

    Delega ao Market Engine (`prices_for_tickers`, cadeia Redis→Postgres do m3) com a
    categoria Cripto — usa o cache cripto e não duplica o SELECT de preço fora da engine
    de mercado. Reusado por `list_wallet_positions` (m4) e pela valoração DeFi (defi_router).
    """
    return await market_service.prices_for_tickers(
        conn, symbols, category=AssetCategory.CRIPTO
    )


async def list_wallet_positions(
    conn: asyncpg.Connection, user_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Saldos escaneados do usuário, valorados pelo preço corrente (m3, asset_prices).

    `value_brl = quantity x price_brl` (None sem preço); `stale` = scan mais velho que
    `ttl_wallet`. Uma varredura do preço (asset_prices) p/ todos os símbolos (sem N+1).
    """
    now = now or datetime.now(tz=UTC)
    rows = await conn.fetch(
        "SELECT chain, wallet_address, asset_symbol, quantity, source, scanned_at, is_manual "
        "FROM wallet_positions WHERE user_id = $1 ORDER BY chain, asset_symbol",
        user_id,
    )
    rows = _prefer_scanned(rows)
    symbols = [r["asset_symbol"] for r in rows]
    prices = await prices_by_ticker(conn, symbols)
    out: list[dict[str, Any]] = []
    for r in rows:
        qty = float(r["quantity"])
        brl, usd = prices.get(r["asset_symbol"], (None, None))
        scanned_at: datetime = r["scanned_at"]
        out.append(
            {
                "chain": r["chain"],
                "wallet_address": r["wallet_address"],
                "asset_symbol": r["asset_symbol"],
                "quantity": qty,
                "source": r["source"],
                "scanned_at": scanned_at.isoformat(),
                "price_brl": brl,
                "price_usd": usd,
                "value_brl": value_of(qty, brl),
                "value_usd": value_of(qty, usd),
                # manual nunca expira (não vem de scan; ADR-012) — só o preço pode envelhecer
                "stale": (
                    False
                    if r["is_manual"]
                    else (now - scanned_at).total_seconds() > settings.ttl_wallet
                ),
                "is_manual": r["is_manual"],
            }
        )
    return out


async def list_defi_valued(
    conn: asyncpg.Connection, user_id: str
) -> list[dict[str, Any]]:
    """Posições DeFi ATIVAS valoradas pelo preço corrente (m3) — mesma valoração do defi_router.

    Helper de serviço compartilhado: o crypto sleeve (valor atual) lê daqui em vez de duplicar
    o SELECT+valoração de `defi_positions`. Sem preço → `value_brl=None` (fail-soft).
    """
    rows = await conn.fetch(
        "SELECT protocol, asset_symbol, balance FROM defi_positions "
        "WHERE user_id = $1 AND is_active",
        user_id,
    )
    prices = await prices_by_ticker(conn, [r["asset_symbol"] for r in rows])
    out: list[dict[str, Any]] = []
    for r in rows:
        bal = float(r["balance"])
        brl, usd = prices.get(r["asset_symbol"], (None, None))
        out.append(
            {
                "protocol": r["protocol"],
                "asset_symbol": r["asset_symbol"],
                "balance": bal,
                "price_brl": brl,
                "value_brl": value_of(bal, brl),
                "value_usd": value_of(bal, usd),
            }
        )
    return out


async def reconcile(conn: asyncpg.Connection, user_id: str) -> list[dict[str, Any]]:
    """Reconcilia saldo escaneado vs registrado: `delta = Σ scanned - net_quantity(ops)`.

    Por símbolo: soma a quantidade escaneada (todas as wallets) e compara com a quantidade
    líquida das `asset_operations`. **Só cripto** (m4): só as carteiras são rastreadas por
    scan; B3 e caixinhas Nubank vêm por outra via e não pertencem à reconciliação. O lado
    escaneado (`wallet_positions`) já é 100% cripto; o registrado é filtrado por categoria.
    """
    # dedup manual vs escaneada (preferindo a escaneada) ANTES de somar — senão contaria 2x
    scanned_rows = _prefer_scanned(
        await conn.fetch(
            "SELECT chain, asset_symbol, quantity, is_manual FROM wallet_positions "
            "WHERE user_id = $1",
            user_id,
        )
    )
    scanned: dict[str, float] = defaultdict(float)
    for r in scanned_rows:
        scanned[r["asset_symbol"]] += float(r["quantity"])

    # categoria case-insensível: op cripto com casing divergente do enum não pode ser dropada
    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade FROM asset_operations "
        "WHERE user_id = $1 AND lower(asset_category) = ANY($2::text[])",
        user_id,
        [c.lower() for c in CRYPTO_CATEGORIES],
    )
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_symbol[op["asset_symbol"]].append(op)
    registered = {sym: net_quantity(rows) for sym, rows in by_symbol.items()}

    symbols = sorted(set(scanned) | set(registered))
    # valoração por símbolo (BRL+USD) reusando o mesmo lookup de preço (sem N+1)
    prices = await prices_by_ticker(conn, symbols)

    out: list[dict[str, Any]] = []
    for sym in symbols:
        s = scanned.get(sym, 0.0)
        reg = registered.get(sym, 0.0)
        brl, usd = prices.get(sym, (None, None))
        out.append(
            {
                "asset_symbol": sym,
                "scanned_quantity": s,
                "registered_quantity": reg,
                "delta": s - reg,
                "value_brl": value_of(s, brl),
                "value_usd": value_of(s, usd),
            }
        )
    return out


async def oldest_scan(conn: asyncpg.Connection) -> datetime | None:
    """Scan de carteira mais antigo — idade real do dado de carteira. Não contam as manuais (como
    a SideSwap) nem a Binance, que só o cron atualiza (no uso local envelheceria e deixaria o
    scan eternamente vencido); a idade da Binance segue visível por posição em /wallets."""
    found: datetime | None = await conn.fetchval(
        "SELECT min(scanned_at) FROM wallet_positions WHERE NOT is_manual AND source <> 'binance'"
    )
    return found


async def positions_as_of(conn: asyncpg.Connection, day: date) -> list[dict[str, Any]]:
    """Carteiras no fim de `day` (Story 5.1): a última linha do histórico ≤ `day` de cada ativo,
    cadeia e endereço, sem as zeradas."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (h.asset_id, h.chain, h.wallet_address)
               h.asset_id, a.price_ref AS asset_symbol, h.chain, h.wallet_address, h.ref_date,
               h.quantity, h.source
        FROM wallet_position_history h JOIN assets a ON a.id = h.asset_id
        WHERE h.ref_date <= $1
        ORDER BY h.asset_id, h.chain, h.wallet_address, h.ref_date DESC
        """,
        day,
    )
    return [dict(r) for r in rows if r["quantity"] > 0]
