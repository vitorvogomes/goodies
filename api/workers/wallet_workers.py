"""Worker wallet_scan (m4) — escaneia saldos de wallet/exchange p/ wallet_positions.

STORY-04-01 entrega o scaffold: agregação **fail-soft por fetcher** dos saldos em
`wallet_positions` (snapshot mais recente). O 04-06 liga os fetchers reais
(Etherscan/Solscan/Liquid/Binance), o job no scheduler (3x/dia 8/14/20h) e a união de
símbolos cripto p/ precificar ativos só-de-wallet. Fetchers injetáveis p/ teste.
"""
from __future__ import annotations

import asyncpg
import structlog

from engines.common.cache import invalidate_xirr_cache
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


def _default_fetchers(*, include_binance: bool = True) -> list[BalanceFetcher]:
    """Os fetchers reais lendo credenciais/endereços de `settings`. Sem credencial
    → o fetcher é no-op (devolve []), então faltar uma fonte não quebra o scan.

    `include_binance=False` no catch-up on-demand: a API assinada da Binance é só via
    cron (CLAUDE.md, decisão 2026-10-17)."""
    fetchers: list[BalanceFetcher] = [
        EtherscanFetcher(),  # ETH (mainnet) + ARB (Arbitrum)
        HyperliquidFetcher(),  # HYPE (Hyperliquid L1)
        SolanaFetcher(),  # SOL + SPL
        LiquidFetcher(),  # L-BTC + USDT (ADR-005)
        BitcoinFetcher(),  # BTC mainchain (ADR-005, client separado do Liquid)
    ]
    if include_binance:
        fetchers.append(BinanceFetcher())  # spot + earn (assinado) — cron only
    return fetchers


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
            # ScanBalances.complete=False → alguma sub-unidade (spec/endereço/endpoint)
            # falhou; lista simples (testes/legado) é tratada como scan completo.
            complete = bool(getattr(balances, "complete", True))
            for balance in balances:
                await service.upsert_wallet_position(conn, user_id, balance)
            # snapshot-replace: posição fechada (vendida/bridada) é varrida — inclusive
            # scan completo e vazio (tudo vendido) nas fontes que o fetcher declara
            # (`SOURCES`); um source fora (incompleto) NÃO apaga o snapshot bom.
            # Scan INCOMPLETO também não varre: a sub-unidade que falhou não é
            # posição fechada (achado C5) — só upserta o que veio.
            swept = (
                await service.sweep_wallet_positions(
                    conn, user_id, balances, getattr(fetcher, "SOURCES", ())
                )
                if complete
                else 0
            )
            stats[name] = {
                "fetched": len(balances),
                "failed": 0 if complete else 1,
                "swept": swept,
            }
    # o scan mudou os saldos cripto → o valor atual do sleeve mudou: invalida o XIRR do
    # usuário (m4) p/ o consolidado/Cripto não ficar stale até o TTL (1h).
    await invalidate_xirr_cache(user_id)
    return stats
