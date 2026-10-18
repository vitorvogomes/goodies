"""run_wallet_scan scaffold — agregação fail-soft por fetcher (m4 STORY-04-01)."""

from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import ScanBalances, WalletBalance
from engines.market.fetchers.wallets.binance import BinanceFetcher
from engines.market.fetchers.wallets.bitcoin import BitcoinFetcher
from engines.market.fetchers.wallets.etherscan import EtherscanFetcher
from engines.market.fetchers.wallets.hyperliquid import HyperliquidFetcher
from engines.market.fetchers.wallets.liquid import LiquidFetcher
from engines.market.fetchers.wallets.solana import SolanaFetcher
from workers.wallet_workers import (
    _default_fetchers,
    resolve_owner_id,
    run_wallet_scan,
)


class _FakeFetcher:
    def __init__(self, balances: list[WalletBalance]) -> None:
        self._balances = balances

    async def fetch(self) -> list[WalletBalance]:
        return self._balances


class _BoomFetcher:
    async def fetch(self) -> list[WalletBalance]:
        raise RuntimeError("chain down")


@pytest.mark.asyncio
async def test_scan_writes_positions(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    fake = _FakeFetcher(
        [
            WalletBalance("ethereum", "0xabc", "ETH", 1.0, "etherscan"),
            WalletBalance("arbitrum", "0xabc", "ARB", 100.0, "etherscan"),
        ]
    )
    stats = await run_wallet_scan(pool, uid, fetchers=[fake])
    assert stats["_FakeFetcher"] == {"fetched": 2, "failed": 0, "swept": 0}
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 2


@pytest.mark.asyncio
async def test_scan_idempotent_rerun(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    fake = _FakeFetcher([WalletBalance("solana", "sol1", "SOL", 5.0, "solscan")])
    await run_wallet_scan(pool, uid, fetchers=[fake])
    await run_wallet_scan(pool, uid, fetchers=[fake])
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 1  # snapshot — não duplica


@pytest.mark.asyncio
async def test_scan_fail_soft_one_fetcher_down(pool: Any, wallet_user: dict) -> None:
    uid = wallet_user["user_id"]
    ok = _FakeFetcher([WalletBalance("liquid", "lq1", "L-BTC", 0.1, "liquid")])
    stats = await run_wallet_scan(pool, uid, fetchers=[_BoomFetcher(), ok])
    assert stats["_BoomFetcher"] == {"fetched": 0, "failed": 1, "swept": 0}
    assert stats["_FakeFetcher"] == {"fetched": 1, "failed": 0, "swept": 0}
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 1  # o fetcher bom grava mesmo com o outro fora


@pytest.mark.asyncio
async def test_scan_sweeps_closed_position(pool: Any, wallet_user: dict) -> None:
    # ETH + ARB no 1º scan; ARB vendido → 2º scan só ETH → ARB é varrido (não fantasma)
    uid = wallet_user["user_id"]
    full = _FakeFetcher(
        [
            WalletBalance("ethereum", "0xabc", "ETH", 1.0, "etherscan"),
            WalletBalance("arbitrum", "0xabc", "ARB", 50.0, "etherscan"),
        ]
    )
    await run_wallet_scan(pool, uid, fetchers=[full])
    only_eth = _FakeFetcher([WalletBalance("ethereum", "0xabc", "ETH", 1.2, "etherscan")])
    stats = await run_wallet_scan(pool, uid, fetchers=[only_eth])
    assert stats["_FakeFetcher"]["swept"] == 1  # ARB removido
    async with pool.acquire() as conn:
        syms = [
            r["asset_symbol"]
            for r in await conn.fetch(
                "SELECT asset_symbol FROM wallet_positions WHERE user_id = $1 "
                "ORDER BY asset_symbol",
                uid,
            )
        ]
    assert syms == ["ETH"]


@pytest.mark.asyncio
async def test_scan_outage_preserves_snapshot(pool: Any, wallet_user: dict) -> None:
    # source fora retorna [] → NÃO varre (outage ≠ posição fechada)
    uid = wallet_user["user_id"]
    f = _FakeFetcher([WalletBalance("solana", "sol1", "SOL", 5.0, "solana")])
    await run_wallet_scan(pool, uid, fetchers=[f])
    await run_wallet_scan(pool, uid, fetchers=[_FakeFetcher([])])  # scan vazio
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 1  # SOL preservado


class _SourcedFetcher(_FakeFetcher):
    """Fetcher que declara as fontes que cobre (como os fetchers reais)."""

    SOURCES = ("bitcoin",)


@pytest.mark.asyncio
async def test_scan_complete_empty_sweeps_declared_source(pool: Any, wallet_user: dict) -> None:
    # Review m4→main: BTC todo vendido → o fetcher escaneia com sucesso e devolve
    # ScanBalances() vazio (complete=True). A posição antiga tem de ser varrida.
    uid = wallet_user["user_id"]
    await run_wallet_scan(
        pool,
        uid,
        fetchers=[_SourcedFetcher([WalletBalance("bitcoin", "bc1", "BTC", 0.1, "bitcoin")])],
    )
    stats = await run_wallet_scan(pool, uid, fetchers=[_SourcedFetcher(ScanBalances())])
    assert stats["_SourcedFetcher"] == {"fetched": 0, "failed": 0, "swept": 1}
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 0


@pytest.mark.asyncio
async def test_scan_incomplete_empty_keeps_declared_source(pool: Any, wallet_user: dict) -> None:
    # fonte fora (complete=False) com SOURCES declarado → continua sem varrer
    uid = wallet_user["user_id"]
    await run_wallet_scan(
        pool,
        uid,
        fetchers=[_SourcedFetcher([WalletBalance("bitcoin", "bc1", "BTC", 0.1, "bitcoin")])],
    )
    await run_wallet_scan(pool, uid, fetchers=[_SourcedFetcher(ScanBalances(complete=False))])
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM wallet_positions WHERE user_id = $1", uid)
    assert n == 1


def test_real_fetchers_declare_sources() -> None:
    # todo fetcher real declara as fontes que cobre (habilita o sweep de scan vazio)
    for f in _default_fetchers():
        assert getattr(type(f), "SOURCES", ()), type(f).__name__
    assert set(HyperliquidFetcher.SOURCES) == {"hyperliquid", "hyperevm"}


@pytest.mark.asyncio
async def test_scan_partial_source_outage_preserves_other_source(
    pool: Any, wallet_user: dict
) -> None:
    # HYPE em 2 fontes (spot + HyperEVM) com sources DISTINTOS: se uma cai (o fetcher
    # devolve só a outra), o sweep por source NÃO apaga o snapshot bom da que caiu.
    # Regressão do code-review (antes, ambas usavam source=hyperliquid → a HyperEVM sumia).
    uid = wallet_user["user_id"]
    both = _FakeFetcher(
        [
            WalletBalance("hyperliquid", "0xw", "HYPE", 0.00979, "hyperliquid"),
            WalletBalance("hyperevm", "0xw", "HYPE", 0.3108, "hyperevm"),
        ]
    )
    await run_wallet_scan(pool, uid, fetchers=[both])
    # HyperEVM "fora": o fetcher devolve só o spot (source hyperliquid)
    spot_only = _FakeFetcher([WalletBalance("hyperliquid", "0xw", "HYPE", 0.00979, "hyperliquid")])
    stats = await run_wallet_scan(pool, uid, fetchers=[spot_only])
    assert stats["_FakeFetcher"]["swept"] == 0  # nada varrido (source hyperevm intacto)
    async with pool.acquire() as conn:
        chains = sorted(
            r["chain"]
            for r in await conn.fetch("SELECT chain FROM wallet_positions WHERE user_id = $1", uid)
        )
    assert chains == ["hyperevm", "hyperliquid"]  # a posição HyperEVM sobreviveu


@pytest.mark.asyncio
async def test_scan_incomplete_fetch_preserves_snapshot_of_failed_subunit(
    pool: Any, wallet_user: dict
) -> None:
    # Achado C5: Etherscan/Solana/Binance fazem fail-soft POR sub-unidade (spec/endereço/
    # endpoint) e devolvem lista PARCIAL não-vazia sob o mesmo source. O sweep não pode
    # tratar a sub-unidade que falhou como "posição fechada".
    uid = wallet_user["user_id"]
    full = _FakeFetcher(
        [
            WalletBalance("ethereum", "0xabc", "ETH", 1.0, "etherscan"),
            WalletBalance("arbitrum", "0xabc", "ARB", 50.0, "etherscan"),
        ]
    )
    await run_wallet_scan(pool, uid, fetchers=[full])
    # Arbitrum "fora": o fetcher devolve só ETH e marca o scan como incompleto
    partial = _FakeFetcher(
        ScanBalances(
            [WalletBalance("ethereum", "0xabc", "ETH", 1.2, "etherscan")],
            complete=False,
        )
    )
    stats = await run_wallet_scan(pool, uid, fetchers=[partial])
    assert stats["_FakeFetcher"] == {"fetched": 1, "failed": 1, "swept": 0}
    async with pool.acquire() as conn:
        syms = sorted(
            r["asset_symbol"]
            for r in await conn.fetch(
                "SELECT asset_symbol FROM wallet_positions WHERE user_id = $1", uid
            )
        )
    assert syms == ["ARB", "ETH"]  # ARB preservado; ETH atualizado


@pytest.mark.asyncio
async def test_scan_empty_list_is_noop(pool: Any, wallet_user: dict) -> None:
    # lista vazia explícita (NÃO os defaults reais — evita rede no teste)
    uid = wallet_user["user_id"]
    assert await run_wallet_scan(pool, uid, fetchers=[]) == {}


def test_default_fetchers_are_the_six() -> None:
    # o caminho default liga os 6 fetchers reais (sem chamar .fetch() — sem rede)
    types = [type(f) for f in _default_fetchers()]
    assert types == [
        EtherscanFetcher,
        HyperliquidFetcher,
        SolanaFetcher,
        LiquidFetcher,
        BitcoinFetcher,
        BinanceFetcher,
    ]


@pytest.mark.asyncio
async def test_resolve_owner_id_returns_a_user(pool: Any, wallet_user: dict) -> None:
    uid = await resolve_owner_id(pool)
    assert uid is not None and isinstance(uid, str)
