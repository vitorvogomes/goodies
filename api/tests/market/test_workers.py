"""Workers de preço (STORY-03-05/06) + wiring do scheduler.

Corpos rodados direto (sem cron) com fetchers FALSOS — sem rede. Verifica gravação em
Postgres (is_manual=False) + Redis, precedência is_manual, idempotência, e a cadência
do scheduler (sem viajar no tempo).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from engines.common.cache import PriceCache
from engines.market import service
from engines.market.fetchers.base import PriceQuote
from workers.price_workers import run_price_b3, run_price_crypto
from workers.scheduler import build_scheduler


class _FakeFetcher:
    """Fetcher de teste: devolve preços fixos só p/ os símbolos conhecidos."""

    def __init__(self, prices: dict[str, PriceQuote]) -> None:
        self._prices = prices

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        return {s: self._prices[s] for s in symbols if s in self._prices}


async def _add_op(pool: Any, uid: str, sym: str, cat: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', $2, $3, 'compra', 10, 5, '2026-01-01')",
            uid,
            sym,
            cat,
        )


@pytest.mark.asyncio
async def test_b3_worker_writes_postgres_and_redis(pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    await _add_op(pool, uid, "MKT_PETR4", "Ações Nacionais")
    fake = _FakeFetcher({"MKT_PETR4": PriceQuote(price_brl=28.5, price_usd=None, source="brapi")})
    empty = _FakeFetcher({})
    stats = await run_price_b3(pool, brapi=fake, treasury=empty)

    assert stats["b3"]["updated"] == 1
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT price_brl, is_manual, source FROM asset_prices WHERE ticker = 'MKT_PETR4'"
        )
    assert float(row["price_brl"]) == 28.5
    assert row["is_manual"] is False
    assert row["source"] == "brapi"
    cache = PriceCache()
    hit = await cache.get(service.price_cache_key("b3", "MKT_PETR4"))
    assert hit is not None and hit["price_brl"] == 28.5
    await cache.delete(service.price_cache_key("b3", "MKT_PETR4"))


@pytest.mark.asyncio
async def test_worker_does_not_overwrite_manual(pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    await _add_op(pool, uid, "MKT_FLASH", "Ações Nacionais")
    async with pool.acquire() as conn:
        await service.upsert_price(
            conn, "MKT_FLASH", 100.0, source="manual", is_manual=True
        )
    fake = _FakeFetcher({"MKT_FLASH": PriceQuote(price_brl=999.0, price_usd=None, source="brapi")})
    stats = await run_price_b3(pool, brapi=fake, treasury=_FakeFetcher({}))

    assert stats["b3"]["skipped"] == 1
    assert stats["b3"]["updated"] == 0
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT price_brl, is_manual FROM asset_prices WHERE ticker = 'MKT_FLASH'"
        )
    assert float(row["price_brl"]) == 100.0  # preço manual intacto
    assert row["is_manual"] is True


@pytest.mark.asyncio
async def test_crypto_worker_writes_usd(pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    await _add_op(pool, uid, "MKT_BTC", "Cripto")
    fake = _FakeFetcher(
        {"MKT_BTC": PriceQuote(price_brl=350000.0, price_usd=65000.0, source="coingecko")}
    )
    stats = await run_price_crypto(pool, fetcher=fake)
    assert stats["updated"] == 1
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT price_brl, price_usd FROM asset_prices WHERE ticker = 'MKT_BTC'"
        )
    assert float(row["price_brl"]) == 350000.0
    assert float(row["price_usd"]) == 65000.0
    await PriceCache().delete(service.price_cache_key("crypto", "MKT_BTC"))


@pytest.mark.asyncio
async def test_idempotent_rerun_same_state(pool: Any, portfolio_user: dict) -> None:
    uid = portfolio_user["user_id"]
    await _add_op(pool, uid, "MKT_ITSA4", "Ações Nacionais")
    fake = _FakeFetcher({"MKT_ITSA4": PriceQuote(price_brl=9.0, price_usd=None, source="brapi")})
    await run_price_b3(pool, brapi=fake, treasury=_FakeFetcher({}))
    await run_price_b3(pool, brapi=fake, treasury=_FakeFetcher({}))  # 2x
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM asset_prices WHERE ticker = 'MKT_ITSA4'")
        price = await conn.fetchval("SELECT price_brl FROM asset_prices WHERE ticker = 'MKT_ITSA4'")
    assert n == 1  # ON CONFLICT: uma linha só
    assert float(price) == 9.0
    await PriceCache().delete(service.price_cache_key("b3", "MKT_ITSA4"))


@pytest.mark.asyncio
async def test_no_holdings_zero_stats(pool: Any) -> None:
    # nenhum símbolo nas categorias (fetcher nunca chamado para esses) -> zeros, sem erro
    stats = await run_price_crypto(pool, fetcher=_FakeFetcher({}))
    assert stats["fetched"] == 0
    assert stats["failed"] == stats["symbols"]


@pytest.mark.asyncio
async def test_crypto_worker_prices_wallet_only_symbol(pool: Any, portfolio_user: dict) -> None:
    # cripto que só existe em wallet_positions (sem op) também recebe preço (m4 B3)
    uid = portfolio_user["user_id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
            "quantity, source) VALUES ($1, 'liquid', 'lq1', 'MKT_WLBTC', 0.1, 'liquid')",
            uid,
        )
    fake = _FakeFetcher(
        {"MKT_WLBTC": PriceQuote(price_brl=300000.0, price_usd=55000.0, source="coingecko")}
    )
    try:
        stats = await run_price_crypto(pool, fetcher=fake)
        assert stats["updated"] == 1
        async with pool.acquire() as conn:
            price = await conn.fetchval(
                "SELECT price_brl FROM asset_prices WHERE ticker = 'MKT_WLBTC'"
            )
        assert float(price) == 300000.0
    finally:
        # limpa wallet_positions ANTES do teardown do usuário (FK sem cascade)
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await PriceCache().delete(service.price_cache_key("crypto", "MKT_WLBTC"))


@pytest.mark.asyncio
async def test_failed_counts_only_core_symbols(pool: Any, portfolio_user: dict) -> None:
    # ticker só-de-wallet fora do mapa do fetcher NÃO infla `failed` (não há fonte p/ ele)
    uid = portfolio_user["user_id"]
    await _add_op(pool, uid, "MKT_COREBTC", "Cripto")
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
            "quantity, source) VALUES ($1, 'solana', 'sol1', 'MKT_DUST', 1, 'solana')",
            uid,
        )
    fake = _FakeFetcher(
        {"MKT_COREBTC": PriceQuote(price_brl=1.0, price_usd=None, source="coingecko")}
    )
    try:
        stats = await run_price_crypto(pool, fetcher=fake)
        assert stats["fetched"] == 1
        assert stats["failed"] == 0  # MKT_DUST (extra de wallet) não conta como falha
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await PriceCache().delete(service.price_cache_key("crypto", "MKT_COREBTC"))


class _MappedFakeFetcher(_FakeFetcher):
    """Fetcher com mapa de símbolos (como o CoinGecko): `supports` diz o que tem fonte."""

    def supports(self, symbol: str) -> bool:
        return symbol in self._prices


@pytest.mark.asyncio
async def test_unmapped_only_extras_are_not_a_blackout(pool: Any, portfolio_user: dict) -> None:
    # review m4→main: só extras SEM mapeamento (ex.: YT-XSOL) e zero cotações não é
    # apagão da fonte — o fetcher nem consultaria a API. Não pode marcar `partial`.
    uid = portfolio_user["user_id"]
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM asset_operations WHERE asset_category = 'Cripto'")
        await conn.execute(
            "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, "
            "quantity, source) VALUES ($1, 'solana', 'sol1', 'MKT_UNMAPPED', 1, 'solana')",
            uid,
        )
    try:
        stats = await run_price_crypto(pool, fetcher=_MappedFakeFetcher({}))
        assert stats["fetched"] == 0
        assert stats["failed"] == 0
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)


@pytest.mark.asyncio
async def test_distinct_symbols_guard_is_fail_soft() -> None:
    # tabela ausente / SELECT falha → [] (não derruba o cron de preço cripto do m3)
    from workers.price_workers import _distinct_symbols

    class _BoomConn:
        async def fetch(self, *_a: Any, **_k: Any) -> list[Any]:
            raise RuntimeError("relation does not exist")

    got = await _distinct_symbols(
        _BoomConn(),  # type: ignore[arg-type]
        "SELECT DISTINCT asset_symbol FROM wallet_positions",
        "wallet",
    )
    assert got == []


@pytest.mark.asyncio
async def test_crypto_worker_prices_defi_only_symbol(pool: Any, portfolio_user: dict) -> None:
    # ativo que só existe em defi_positions (sem op/wallet) também recebe preço (m4)
    uid = portfolio_user["user_id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO defi_positions (user_id, asset_symbol, balance, is_active) "
            "VALUES ($1, 'MKT_DEFI', 5, true)",
            uid,
        )
    fake = _FakeFetcher({"MKT_DEFI": PriceQuote(price_brl=12.0, price_usd=2.0, source="coingecko")})
    try:
        stats = await run_price_crypto(pool, fetcher=fake)
        assert stats["updated"] == 1
        async with pool.acquire() as conn:
            price = await conn.fetchval(
                "SELECT price_brl FROM asset_prices WHERE ticker = 'MKT_DEFI'"
            )
        assert float(price) == 12.0
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", uid)
        await PriceCache().delete(service.price_cache_key("crypto", "MKT_DEFI"))


@pytest.mark.asyncio
async def test_defi_distinct_symbols_guard_is_fail_soft() -> None:
    # tabela ausente / SELECT falha → [] (não derruba o cron de preço cripto)
    from workers.price_workers import _distinct_symbols

    class _BoomConn:
        async def fetch(self, *_a: Any, **_k: Any) -> list[Any]:
            raise RuntimeError("relation defi_positions does not exist")

    got = await _distinct_symbols(
        _BoomConn(),  # type: ignore[arg-type]
        "SELECT DISTINCT asset_symbol FROM defi_positions WHERE is_active",
        "defi",
    )
    assert got == []


def test_scheduler_registers_jobs_with_cadence() -> None:
    scheduler = build_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert set(jobs) == {
        "price_b3",
        "price_crypto",
        "wallet_scan",
        "benchmark_daily",
        "db_backup",
        "restore_check",
        "rf_cdi",  # Story 7.4: renda fixa pelo CDI real, depois do benchmark das 22h
        "price_history",  # v2.2: um ano de preço diário, dia 2 de cada mês (ADR-019)
    }
    # inspeciona os triggers sem iniciar o scheduler (não viaja no tempo)
    b3 = str(jobs["price_b3"].trigger)
    assert "day_of_week='mon-fri'" in b3
    assert "hour='19'" in b3  # 1x/dia útil após fechamento (free-tier BRAPI)
    assert "hour='*/2'" in str(jobs["price_crypto"].trigger)
    assert "hour='8,14,20'" in str(jobs["wallet_scan"].trigger)  # 3x/dia (m4)
    assert "hour='22'" in str(jobs["benchmark_daily"].trigger)  # 1x/dia (m4)
    rf = str(jobs["rf_cdi"].trigger)
    assert "hour='22'" in rf and "minute='20'" in rf
    assert "hour='13'" in str(jobs["db_backup"].trigger)  # Story 1.2: 1x/dia
    assert "day='1'" in str(jobs["restore_check"].trigger)  # Story 1.2: dia 1 de cada mês
