"""Worker wallet_scan (m4) — escaneia saldos de wallet/exchange p/ wallet_positions.

STORY-04-01 entrega o scaffold: agregação **fail-soft por fetcher** dos saldos em
`wallet_positions` (snapshot mais recente). O 04-06 liga os fetchers reais
(Etherscan/Solscan/Liquid/Binance), o job no scheduler (3x/dia 8/14/20h) e a união de
símbolos cripto p/ precificar ativos só-de-wallet. Fetchers injetáveis p/ teste.
"""
from __future__ import annotations

import asyncpg
import structlog

from engines.market.fetchers.wallets.base import BalanceFetcher
from engines.market.fetchers.wallets.binance import BinanceFetcher
from engines.market.fetchers.wallets.bitcoin import BitcoinFetcher
from engines.market.fetchers.wallets.etherscan import EtherscanFetcher
from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher
from engines.market.fetchers.wallets.liquid import LiquidFetcher
from engines.market.fetchers.wallets.solana import SolanaFetcher
from engines.wallet import service

logger = structlog.get_logger()


async def resolve_owner_id(pool: asyncpg.Pool) -> str | None:
    """Dono do scan (usuário único no MVP, §3.7). None se não houver usuário."""
    async with pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users ORDER BY created_at LIMIT 1")
    return str(uid) if uid is not None else None


def _default_fetchers() -> list[BalanceFetcher]:
    """Os 5 fetchers reais lendo credenciais/endereços de `settings`. Sem credencial
    → o fetcher é no-op (devolve []), então faltar uma fonte não quebra o scan."""
    return [
        EtherscanFetcher(),  # ETH (mainnet) + ARB (Arbitrum)
        HyperliquidFetcher(),  # HYPE (Hyperliquid L1)
        SolanaFetcher(),  # SOL + SPL
        LiquidFetcher(),  # L-BTC + USDT (ADR-005)
        BitcoinFetcher(),  # BTC mainchain (ADR-005, client separado do Liquid)
        BinanceFetcher(),  # spot + earn (assinado)
    ]


async def run_wallet_scan(
    pool: asyncpg.Pool,
    user_id: str,
    *,
    fetchers: list[BalanceFetcher] | None = None,
) -> dict[str, dict[str, int]]:
    """Roda cada fetcher e grava os saldos em wallet_positions (snapshot mais recente).

    Fail-soft por fetcher: uma chain/exchange fora (ou que levante) não bloqueia as
    demais nem propaga exceção. Devolve estatísticas por fetcher: {fetched, failed}.
    """
    fetchers = fetchers if fetchers is not None else _default_fetchers()
    stats: dict[str, dict[str, int]] = {}
    async with pool.acquire() as conn:
        for fetcher in fetchers:
            name = type(fetcher).__name__
            try:
                balances = await fetcher.fetch()
            except Exception as exc:  # defesa extra; os fetchers já são fail-soft
                logger.warning("wallet_scan_fetcher_failed", fetcher=name, error=str(exc))
                stats[name] = {"fetched": 0, "failed": 1, "swept": 0}
                continue
            for balance in balances:
                await service.upsert_wallet_position(conn, user_id, balance)
            # snapshot-replace: posição fechada (vendida/bridada) é varrida; um source
            # fora devolve [] e NÃO apaga o último snapshot bom (outage ≠ fechamento).
            swept = await service.sweep_wallet_positions(conn, user_id, balances)
            stats[name] = {"fetched": len(balances), "failed": 0, "swept": swept}
    return stats
