"""Contrato base dos fetchers (retry/backoff) — puro, sem rede."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.base import PriceQuote, with_client, with_retry


async def _no_sleep(_d: float) -> None: ...


class _FakeClient:
    """Dublê de httpx.AsyncClient: só rastreia se foi fechado."""

    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


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


# --------------------------------------------------------------------------- #
# with_client — scaffold "client próprio-ou-injetado + with_retry" (B0#1 m4)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_with_client_closes_owned_client() -> None:
    created: list[_FakeClient] = []

    def factory() -> Any:
        c = _FakeClient()
        created.append(c)
        return c

    async def do(_c: Any) -> str:
        return "ok"

    out = await with_client(do, sleep=_no_sleep, factory=factory)
    assert out == "ok"
    assert created and created[0].closed is True  # client próprio é fechado


@pytest.mark.asyncio
async def test_with_client_leaves_injected_client_open() -> None:
    c = _FakeClient()

    async def do(_c: Any) -> str:
        return "ok"

    out = await with_client(do, client=c, sleep=_no_sleep)
    assert out == "ok"
    assert c.closed is False  # client injetado NÃO é fechado (dono é o chamador)


@pytest.mark.asyncio
async def test_with_client_passes_client_and_retries() -> None:
    slept: list[float] = []
    calls: list[Any] = []
    c = _FakeClient()

    async def do(client: Any) -> str:
        calls.append(client)
        if len(calls) < 2:
            raise ValueError("boom")
        return "ok"

    async def sleep(d: float) -> None:
        slept.append(d)

    out = await with_client(do, client=c, sleep=sleep)
    assert out == "ok"
    assert calls == [c, c]  # o mesmo client é passado ao do_request
    assert slept == [1.0]  # 1 retry com backoff 1s


@pytest.mark.asyncio
async def test_with_client_reraises_and_closes_owned_on_error() -> None:
    created: list[_FakeClient] = []

    def factory() -> Any:
        c = _FakeClient()
        created.append(c)
        return c

    async def do(_c: Any) -> str:
        raise ValueError("always")

    with pytest.raises(ValueError, match="always"):
        await with_client(do, sleep=_no_sleep, attempts=2, factory=factory)
    assert created[0].closed is True  # fecha o client próprio mesmo com erro
