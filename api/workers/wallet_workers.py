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
from engines.wallet import service

logger = structlog.get_logger()


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
    fetchers = fetchers if fetchers is not None else []
    stats: dict[str, dict[str, int]] = {}
    async with pool.acquire() as conn:
        for fetcher in fetchers:
            name = type(fetcher).__name__
            try:
                balances = await fetcher.fetch()
            except Exception as exc:  # defesa extra; os fetchers já são fail-soft
                logger.warning("wallet_scan_fetcher_failed", fetcher=name, error=str(exc))
                stats[name] = {"fetched": 0, "failed": 1}
                continue
            for balance in balances:
                await service.upsert_wallet_position(conn, user_id, balance)
            stats[name] = {"fetched": len(balances), "failed": 0}
    return stats
