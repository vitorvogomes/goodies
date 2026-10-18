"""§3.4: upsert_price é o chokepoint único de escrita de preço.

Duas garantias críticas para o Market Engine (m3):
1. Precedência is_manual — o worker (is_manual=False) NUNCA sobrescreve uma linha
   manual (Flash/RF/caixinhas/DeFi, sem fonte de mercado). Manual sempre vence.
2. Invalida o cache de XIRR de todo usuário que detém o ticker (ADR-008) — antes a
   invalidação estava só no router do PUT; o worker chamaria upsert_price direto.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
import pytest

from engines.common.cache import PriceCache
from engines.portfolio import service


async def _price_row(conn: asyncpg.Connection, ticker: str) -> Any:
    return await conn.fetchrow(
        "SELECT price_brl, source, is_manual FROM asset_prices WHERE ticker = $1",
        ticker,
    )


@pytest.mark.asyncio
async def test_worker_does_not_overwrite_manual(pool: Any, portfolio_user: dict) -> None:
    async with pool.acquire() as conn:
        await service.upsert_price(conn, "FLASHX", 100.0, source="manual", is_manual=True)
        # worker tenta sobrescrever — deve ser ignorado
        await service.upsert_price(conn, "FLASHX", 999.0, source="brapi", is_manual=False)
        row = await _price_row(conn, "FLASHX")
    assert float(row["price_brl"]) == 100.0
    assert row["is_manual"] is True
    assert row["source"] == "manual"


@pytest.mark.asyncio
async def test_worker_overwrites_non_manual(pool: Any, portfolio_user: dict) -> None:
    async with pool.acquire() as conn:
        await service.upsert_price(conn, "PETR4", 30.0, source="b3", is_manual=False)
        await service.upsert_price(conn, "PETR4", 31.5, source="brapi", is_manual=False)
        row = await _price_row(conn, "PETR4")
    assert float(row["price_brl"]) == 31.5
    assert row["is_manual"] is False


@pytest.mark.asyncio
async def test_worker_inserts_new_ticker(pool: Any, portfolio_user: dict) -> None:
    async with pool.acquire() as conn:
        result = await service.upsert_price(
            conn, "NEWX", 12.0, source="brapi", is_manual=False
        )
        row = await _price_row(conn, "NEWX")
    assert float(row["price_brl"]) == 12.0
    assert row["is_manual"] is False
    assert result["ticker"] == "NEWX"


@pytest.mark.asyncio
async def test_manual_always_overwrites_worker(pool: Any, portfolio_user: dict) -> None:
    async with pool.acquire() as conn:
        await service.upsert_price(conn, "ITSA4", 9.0, source="brapi", is_manual=False)
        await service.upsert_price(conn, "ITSA4", 10.0, source="manual", is_manual=True)
        row = await _price_row(conn, "ITSA4")
    assert float(row["price_brl"]) == 10.0
    assert row["is_manual"] is True


@pytest.mark.asyncio
async def test_manual_brl_edit_preserves_existing_usd(
    pool: Any, portfolio_user: dict
) -> None:
    """Edição manual só de BRL não apaga o price_usd já gravado (ex.: cripto)."""
    async with pool.acquire() as conn:
        await service.upsert_price(
            conn, "BTCX", 350000.0, price_usd=65000.0, source="coingecko", is_manual=False
        )
        # override manual de BRL, sem informar USD
        await service.upsert_price(conn, "BTCX", 360000.0)
        row = await conn.fetchrow(
            "SELECT price_brl, price_usd FROM asset_prices WHERE ticker = 'BTCX'"
        )
    assert float(row["price_brl"]) == 360000.0
    assert row["price_usd"] is not None
    assert float(row["price_usd"]) == 65000.0  # USD preservado


@pytest.mark.asyncio
async def test_upsert_invalidates_xirr_cache_of_holder(
    pool: Any, portfolio_user: dict
) -> None:
    uid = portfolio_user["user_id"]
    cache = PriceCache()
    key = f"xirr:consolidated:{uid}"  # convenção ADR-008
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
            "asset_category, tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'CACHEX', 'Ações Nacionais', 'compra', 10, 5, $2)",
            uid,
            date(2026, 1, 1),
        )
        await cache.set(key, {"consolidated": 0.1}, 3600)
        assert await cache.get(key) is not None
        await service.upsert_price(conn, "CACHEX", 6.0, source="brapi", is_manual=False)
        assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_upsert_same_price_keeps_xirr_cache(
    pool: Any, portfolio_user: dict
) -> None:
    """Worker re-rodando com o MESMO preço NÃO invalida o XIRR (§debito m3 #3): o cache
    de XIRR (TTL 1h) raramente sobreviveria à cadência cripto (*/2h) se flushasse sempre."""
    uid = portfolio_user["user_id"]
    cache = PriceCache()
    key = f"xirr:consolidated:{uid}"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
            "asset_category, tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'SAMEX', 'Ações Nacionais', 'compra', 10, 5, $2)",
            uid,
            date(2026, 1, 1),
        )
        await service.upsert_price(conn, "SAMEX", 7.0, source="brapi", is_manual=False)
        # prima o cache DEPOIS do baseline (esse 1º upsert já teria invalidado)
        await cache.set(key, {"consolidated": 0.1}, 3600)
        # mesmo preço → cache preservado
        await service.upsert_price(conn, "SAMEX", 7.0, source="brapi", is_manual=False)
        assert await cache.get(key) is not None
        # preço diferente → invalida
        await service.upsert_price(conn, "SAMEX", 7.5, source="brapi", is_manual=False)
        assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_upsert_usd_only_change_keeps_xirr_cache(
    pool: Any, portfolio_user: dict
) -> None:
    """Mudar SÓ price_usd não invalida o XIRR (que é em BRL) — evita churn de cache."""
    uid = portfolio_user["user_id"]
    cache = PriceCache()
    key = f"xirr:consolidated:{uid}"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
            "asset_category, tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', 'USDX', 'Cripto', 'compra', 1, 100, $2)",
            uid,
            date(2026, 1, 1),
        )
        await service.upsert_price(
            conn, "USDX", 100.0, price_usd=20.0, source="coingecko", is_manual=False
        )
        await cache.set(key, {"consolidated": 0.1}, 3600)
        # mesmo BRL, USD diferente → XIRR (BRL) preservado
        await service.upsert_price(
            conn, "USDX", 100.0, price_usd=25.0, source="coingecko", is_manual=False
        )
        assert await cache.get(key) is not None
        # BRL muda → invalida
        await service.upsert_price(
            conn, "USDX", 110.0, price_usd=25.0, source="coingecko", is_manual=False
        )
        assert await cache.get(key) is None
