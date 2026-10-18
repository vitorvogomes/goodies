"""Story 2.1 — owner único, cache único (com invalidação do XIRR) e MonthStatusPort."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.common import cache as common_cache
from engines.common.month_status import AllMonthsOpen, month_status, register_month_status
from engines.common.owner import NoOwnerError, get_owner_id


@pytest.mark.asyncio
async def test_owner_is_first_user(pool: Any) -> None:
    async with pool.acquire() as conn:
        first = await conn.fetchval("SELECT id FROM users ORDER BY created_at LIMIT 1")
        if first is None:
            with pytest.raises(NoOwnerError):
                await get_owner_id(conn)
        else:
            assert await get_owner_id(conn) == str(first)


def test_cache_is_single_instance_and_swappable() -> None:
    a = common_cache.cache()
    assert common_cache.cache() is a
    other = common_cache.PriceCache()
    previous = common_cache.use_cache(other)
    try:
        assert common_cache.cache() is other
    finally:
        common_cache.use_cache(previous)
    assert common_cache.cache() is a


@pytest.mark.asyncio
async def test_invalidate_xirr_cache_deletes_user_key() -> None:
    c = common_cache.cache()
    await c.set(common_cache.xirr_key("u-1"), {"consolidated": 0.1}, 60)
    assert await c.get(common_cache.xirr_key("u-1")) is not None
    await common_cache.invalidate_xirr_cache("u-1")
    assert await c.get(common_cache.xirr_key("u-1")) is None


@pytest.mark.asyncio
async def test_default_month_status_is_all_open() -> None:
    port = AllMonthsOpen()
    assert await port.status(None, date(2026, 6, 1)) == "aberto"
    assert await port.is_closed(None, date(2026, 6, 1)) is False
    await port.mark_dirty(None, date(2026, 6, 1))  # no-op


def test_registry_returns_registered_port() -> None:
    class Fake(AllMonthsOpen):
        pass

    previous = month_status()
    fake = Fake()
    register_month_status(fake)
    try:
        assert month_status() is fake
    finally:
        register_month_status(previous)


def test_main_registers_a_port() -> None:
    import main  # noqa: F401  (o import faz os registros)

    assert month_status() is not None
