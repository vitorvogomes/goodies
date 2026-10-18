"""Fetcher BCB — séries de benchmark CDI/IPCA (SGS open data). STORY-04-07.

API pública do Banco Central (SGS), sem auth/quota:
`GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/1?formato=json`
→ `[{"data": "dd/mm/aaaa", "valor": "0.053"}]`; por intervalo (Story 7.2), `.../dados?formato=json
&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa` → todos os pontos do período.
Séries: **CDI = 12** (taxa diária %), **IPCA = 433** (variação mensal %).

Devolve `BenchmarkPoint`s normalizados; a valoração/uso pleno (acumulado, retorno real) é
do m5. Fail-soft (CLAUDE.md): série fora → omitida; tudo fora → lista vazia, nunca levanta.
IBOV não entra aqui (deferido ao m5, story 05-03).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from .base import with_client

_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
_SOURCE = "bcb"
# série SGS → nome do benchmark. CDI diário (12), IPCA mensal (433).
_DEFAULT_SERIES: dict[str, int] = {"CDI": 12, "IPCA": 433}


@dataclass(frozen=True)
class BenchmarkPoint:
    """Ponto de uma série de benchmark (valor na data-base)."""

    series: str  # CDI | IPCA | IBOV
    ref_date: date
    value: float
    source: str


def _parse_date(s: str) -> date | None:
    try:
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


class BcbFetcher:
    """Cota CDI/IPCA pelo SGS do BCB. `series`/`client`/`sleep` injetáveis p/ teste."""

    def __init__(
        self,
        series: dict[str, int] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._series = series if series is not None else _DEFAULT_SERIES
        self._client = client
        self._sleep = sleep

    async def fetch(self) -> list[BenchmarkPoint]:
        out: list[BenchmarkPoint] = []
        client = self._client or httpx.AsyncClient()
        try:
            for name, code in self._series.items():

                async def _req(c: httpx.AsyncClient, code: int = code) -> Any:
                    return await self._latest(c, code)

                try:
                    data = await with_client(_req, client=client, sleep=self._sleep)
                except Exception:
                    continue  # fail-soft por série
                point = self._parse(name, data)
                if point is not None:
                    out.append(point)
        finally:
            if self._client is None:
                await client.aclose()
        return out

    async def fetch_range(self, start: date, end: date) -> list[BenchmarkPoint]:
        """Todos os pontos de cada série entre `start` e `end` (fail-soft por série)."""
        out: list[BenchmarkPoint] = []
        client = self._client or httpx.AsyncClient()
        params = {
            "formato": "json",
            "dataInicial": f"{start:%d/%m/%Y}",
            "dataFinal": f"{end:%d/%m/%Y}",
        }
        try:
            for name, code in self._series.items():

                async def _req(c: httpx.AsyncClient, code: int = code) -> Any:
                    resp = await c.get(f"{_BASE_URL}.{code}/dados", params=params, timeout=30.0)
                    resp.raise_for_status()
                    return resp.json()

                try:
                    data = await with_client(_req, client=client, sleep=self._sleep)
                except Exception:
                    continue  # fail-soft por série
                if not isinstance(data, list):
                    continue
                for row in data:
                    point = self._parse(name, [row])
                    if point is not None:
                        out.append(point)
        finally:
            if self._client is None:
                await client.aclose()
        return out

    async def _latest(self, client: httpx.AsyncClient, code: int) -> Any:
        resp = await client.get(
            f"{_BASE_URL}.{code}/dados/ultimos/1", params={"formato": "json"}, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse(name: str, data: Any) -> BenchmarkPoint | None:
        if not isinstance(data, list) or not data:
            return None
        row = data[-1]
        if not isinstance(row, dict):
            return None
        ref = _parse_date(str(row.get("data", "")))
        raw_value = row.get("valor")
        if ref is None or raw_value is None:
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        return BenchmarkPoint(series=name, ref_date=ref, value=value, source=_SOURCE)
