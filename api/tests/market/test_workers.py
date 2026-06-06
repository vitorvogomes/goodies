"""Workers de preço (STORY-03-05/06) + wiring do scheduler.

Corpos rodados direto (sem cron) com fetchers FALSOS — sem rede. Verifica gravação em
Postgres (is_manual=False) + Redis, precedência is_manual, idempotência, e a cadência
do scheduler (sem viajar no tempo).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from engines.market import service
from engines.market.cache import PriceCache
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
    fake = _FakeFetcher(
        {"MKT_PETR4": PriceQuote(price_brl=28.5, price_usd=None, source="brapi")}
    )
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
        await service.portfolio_service.upsert_price(
            conn, "MKT_FLASH", 100.0, source="manual", is_manual=True
        )
    fake = _FakeFetcher(
        {"MKT_FLASH": PriceQuote(price_brl=999.0, price_usd=None, source="brapi")}
    )
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
    fake = _FakeFetcher(
        {"MKT_ITSA4": PriceQuote(price_brl=9.0, price_usd=None, source="brapi")}
    )
    await run_price_b3(pool, brapi=fake, treasury=_FakeFetcher({}))
    await run_price_b3(pool, brapi=fake, treasury=_FakeFetcher({}))  # 2x
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM asset_prices WHERE ticker = 'MKT_ITSA4'"
        )
        price = await conn.fetchval(
            "SELECT price_brl FROM asset_prices WHERE ticker = 'MKT_ITSA4'"
        )
    assert n == 1  # ON CONFLICT: uma linha só
    assert float(price) == 9.0
    await PriceCache().delete(service.price_cache_key("b3", "MKT_ITSA4"))


@pytest.mark.asyncio
async def test_no_holdings_zero_stats(pool: Any) -> None:
    # nenhum símbolo nas categorias (fetcher nunca chamado para esses) -> zeros, sem erro
    stats = await run_price_crypto(pool, fetcher=_FakeFetcher({}))
    assert stats["fetched"] == 0
    assert stats["failed"] == stats["symbols"]


def test_scheduler_registers_jobs_with_cadence() -> None:
    scheduler = build_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert set(jobs) == {"price_b3", "price_crypto"}
    # inspeciona os triggers sem iniciar o scheduler (não viaja no tempo)
    b3 = str(jobs["price_b3"].trigger)
    assert "day_of_week='mon-fri'" in b3
    assert "hour='9-18/4'" in b3
    assert "hour='*/2'" in str(jobs["price_crypto"].trigger)
