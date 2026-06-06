"""Contrato base dos fetchers (retry/backoff) — puro, sem rede."""
from __future__ import annotations

import pytest

from engines.market.fetchers.base import PriceQuote, with_retry


async def _no_sleep(_d: float) -> None: ...


@pytest.mark.asyncio
async def test_succeeds_first_try() -> None:
    calls = []

    async def fn() -> str:
        calls.append(1)
        return "ok"

    assert await with_retry(fn, sleep=_no_sleep) == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retries_then_succeeds_with_backoff() -> None:
    calls = []
    slept: list[float] = []

    async def fn() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("boom")
        return "ok"

    async def sleep(d: float) -> None:
        slept.append(d)

    assert await with_retry(fn, attempts=4, base_delay=1.0, sleep=sleep) == "ok"
    assert len(calls) == 3
    assert slept == [1.0, 2.0]  # dormiu antes das tentativas 2 e 3 (a 3ª deu certo)


@pytest.mark.asyncio
async def test_exhausts_and_reraises() -> None:
    async def fn() -> str:
        raise ValueError("always")

    with pytest.raises(ValueError, match="always"):
        await with_retry(fn, attempts=3, base_delay=0, sleep=_no_sleep)


@pytest.mark.asyncio
async def test_backoff_sequence_1_2_4() -> None:
    slept: list[float] = []

    async def fn() -> str:
        raise RuntimeError("nope")

    async def sleep(d: float) -> None:
        slept.append(d)

    with pytest.raises(RuntimeError):
        await with_retry(fn, attempts=4, base_delay=1.0, sleep=sleep)
    assert slept == [1.0, 2.0, 4.0]  # 3 retries -> backoff 1s/2s/4s (CLAUDE.md)


def test_price_quote_fields() -> None:
    q = PriceQuote(price_brl=10.0, price_usd=2.0, source="x")
    assert (q.price_brl, q.price_usd, q.source) == (10.0, 2.0, "x")
