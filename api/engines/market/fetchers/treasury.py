"""Fetcher Tesouro Direto — STORY-03-04. Fonte: Tesouro Transparente (open data).

A API oficial do Tesouro Direto fica atrás de um desafio JS do Cloudflare (403 headless),
então usamos o CSV público "Preços e Taxas dos Títulos Públicos" do Tesouro Transparente
(CKAN do Tesouro Nacional): sem auth, sem WAF, sem quota, atualizado por dia útil; uso livre
citando a fonte.

CSV `;`-separado (latin-1), colunas:
  Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;
  PU Compra Manha;PU Venda Manha;PU Base Manha
Para cada ticker "Tesouro <Tipo> <AAAA>" casa (Tipo Titulo exato, ano do vencimento) na
Data Base mais recente e devolve o PU de venda (resgate). Fail-soft: erro/sem casamento →
símbolo omitido. O CSV (~14MB, histórico) é baixado 1x/dia pelo worker; o parse é single-pass
e de baixa memória (só os símbolos pedidos são guardados).
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence

import httpx

from .base import PriceQuote, with_retry

_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)
_SOURCE = "tesouro"
_TICKER_RE = re.compile(r"^\s*(Tesouro\s+.+?)\s+(\d{4})\s*$")
_DateT = tuple[int, int, int]


def _parse_ticker(symbol: str) -> tuple[str, int] | None:
    """'Tesouro IPCA+ 2040' → ('Tesouro IPCA+', 2040)."""
    m = _TICKER_RE.match(symbol)
    if not m:
        return None
    return " ".join(m.group(1).split()), int(m.group(2))


def _br_float(s: str) -> float | None:
    try:
        return float(s.strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _br_date(s: str) -> _DateT | None:
    try:
        d, mth, y = s.split("/")
        return int(y), int(mth), int(d)
    except ValueError:
        return None


class TreasuryFetcher:
    """Cota Tesouro Direto pelo CSV do Tesouro Transparente. `client`/`sleep` injetáveis."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        # (Tipo, ano) → símbolo original pedido
        wanted: dict[tuple[str, int], str] = {}
        for s in symbols:
            parsed = _parse_ticker(s)
            if parsed is not None:
                wanted[parsed] = s
        if not wanted:
            return {}
        client = self._client or httpx.AsyncClient(follow_redirects=True)
        try:
            text = await with_retry(
                lambda: self._download(client), attempts=4, sleep=self._sleep
            )
        except Exception:
            return {}  # fail-soft: fonte indisponível → nada
        finally:
            if self._client is None:
                await client.aclose()
        return self._parse(text, wanted)

    async def _download(self, client: httpx.AsyncClient) -> str:
        resp = await client.get(_CSV_URL, timeout=60.0)
        resp.raise_for_status()
        return resp.content.decode("latin-1", errors="replace")

    @staticmethod
    def _parse(text: str, wanted: dict[tuple[str, int], str]) -> dict[str, PriceQuote]:
        # single-pass: por símbolo, guarda o PU da maior Data Base vista.
        latest: dict[str, tuple[_DateT, float]] = {}
        for line in text.splitlines():
            p = line.split(";")
            if len(p) < 8:
                continue
            base = _br_date(p[2])
            venc = _br_date(p[1])
            if base is None or venc is None:
                continue  # cabeçalho / linha inválida
            sym = wanted.get((" ".join(p[0].split()), venc[0]))
            if sym is None:
                continue
            pu = _br_float(p[6])  # PU Venda Manha (resgate)
            if pu is None:
                pu = _br_float(p[7])  # fallback PU Base Manha
            if pu is None:
                continue
            prev = latest.get(sym)
            if prev is None or base > prev[0]:
                latest[sym] = (base, pu)
        return {
            sym: PriceQuote(price_brl=pu, price_usd=None, source=_SOURCE)
            for sym, (_base, pu) in latest.items()
        }
