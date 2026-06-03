"""STORY-00-04 — testes do cache Redis (PriceCache + check_redis).

TDD RED-first: estes testes falham enquanto `engines.market.cache` não existe.

Rodam contra o Redis real (docker em redis://localhost:6379/0). Usam o prefixo
`test:cache:` e limpam tudo que criam (fixture `cleanup_keys`). O caso de
fail-soft aponta o cache para uma porta sem servidor (`redis://localhost:6399/0`).
"""

import asyncio
import uuid

import pytest

from engines.market.cache import PriceCache, check_redis

LOCAL_URL = "redis://localhost:6379/0"
UNREACHABLE_URL = "redis://localhost:6399/0"  # nenhum servidor escutando aqui


@pytest.fixture
def test_key() -> str:
    """Chave única por teste, no prefixo de testes, para isolamento."""
    return f"test:cache:{uuid.uuid4().hex}"


@pytest.fixture
async def cache() -> PriceCache:
    return PriceCache(redis_url=LOCAL_URL)


async def test_set_then_get_roundtrip(cache: PriceCache, test_key: str) -> None:
    payload = {"value": 42.5, "stale": False, "ticker": "PETR4"}
    try:
        await cache.set(test_key, payload, ttl_seconds=30)
        result = await cache.get(test_key)
        assert result == payload
    finally:
        await cache.delete(test_key)


async def test_get_missing_key_returns_none(cache: PriceCache, test_key: str) -> None:
    result = await cache.get(test_key)
    assert result is None


async def test_ttl_expiration(cache: PriceCache, test_key: str) -> None:
    await cache.set(test_key, {"value": 1}, ttl_seconds=1)
    # imediatamente disponível
    assert await cache.get(test_key) == {"value": 1}
    # expira após o TTL
    await asyncio.sleep(1.2)
    assert await cache.get(test_key) is None


async def test_delete_removes_key(cache: PriceCache, test_key: str) -> None:
    await cache.set(test_key, {"value": 7}, ttl_seconds=30)
    assert await cache.get(test_key) == {"value": 7}
    await cache.delete(test_key)
    assert await cache.get(test_key) is None


async def test_get_fail_soft_returns_none_when_unreachable() -> None:
    bad_cache = PriceCache(redis_url=UNREACHABLE_URL)
    # não deve levantar exceção — fail-soft (ADR-004)
    assert await bad_cache.get("test:cache:whatever") is None


async def test_set_and_delete_fail_soft_when_unreachable() -> None:
    bad_cache = PriceCache(redis_url=UNREACHABLE_URL)
    # set/delete não devem levantar exceção mesmo com Redis indisponível
    await bad_cache.set("test:cache:whatever", {"value": 1}, ttl_seconds=30)
    await bad_cache.delete("test:cache:whatever")


async def test_check_redis_connected() -> None:
    name, status = await check_redis()
    assert name == "redis"
    assert status == "connected"


async def test_check_redis_disconnected_fail_soft() -> None:
    name, status = await check_redis(redis_url=UNREACHABLE_URL)
    assert name == "redis"
    assert status == "disconnected"
