"""Contrato de fetcher + retry/backoff do Market Engine (m3).

Cada fetcher (BRAPI/CoinGecko/Tesouro) implementa o protocolo `PriceFetcher` e
devolve `PriceQuote` por símbolo. `with_retry` faz o backoff exponencial (1s/2s/4s,
CLAUDE.md); `sleep` é injetável p/ os testes rodarem sem espera real.

Fail-soft (CLAUDE.md): um símbolo sem cotação é **omitido** do resultado — nunca
levanta para cima. Quem escreve em cache/Postgres é o worker; o fetcher só busca.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PriceQuote:
    """Cotação normalizada de um ativo (BRL principal; USD quando a fonte fornece)."""

    price_brl: float
    price_usd: float | None
    source: str


class PriceFetcher(Protocol):
    """Busca preços para um conjunto de símbolos (fail-soft: símbolo sem preço é omitido)."""

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]: ...


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Executa `fn` com backoff exponencial (1s/2s/4s por padrão).

    Repete em qualquer exceção até `attempts`; re-levanta a última se todas falharem.
    `sleep` é injetável (testes passam `base_delay=0` ou um no-op p/ não esperar).
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as exc:
            last = exc
            if i < attempts - 1:
                await sleep(base_delay * (2**i))
    raise last if last is not None else RuntimeError("with_retry: attempts must be >= 1")
