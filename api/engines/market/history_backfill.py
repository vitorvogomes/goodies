"""Histórico diário de preço para a oportunidade nos aportes (v2.2 — F5): a variação de 3 meses e
a máxima de 52 semanas precisam de um ano de preço por ativo, e o `asset_price_history` só tinha
B3 e Tesouro desde 18/10/2026 (o dia em que ele nasceu). Fontes oficiais e sem chave:

- B3: o COTAHIST anual da B3 (`COTAHIST_A{ano}.ZIP`, atualizado a cada pregão): o fechamento
  (PREULT) do mercado à vista dos tickers da carteira. O BRAPI grátis só dá 3 meses.
- Tesouro: o mesmo CSV do Tesouro Transparente do preço diário, agora com todas as datas.
- Cripto: o `market_chart` do CoinGecko (365 dias, o limite grátis).

Grava só os dias que faltam (nunca sobrescreve um preço do histórico) e nunca levanta por fonte
externa: a fonte que falhar fica de fora das estatísticas da rodada.
"""

from __future__ import annotations

import asyncio
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
import httpx

from config import settings
from engines.common.dates import today_brt
from engines.market.fetchers import treasury

COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
DAYS = 400  # um ano e um pouco: a máxima de 52 semanas e a variação de 3 meses com folga

Point = tuple[date, Decimal]


# ---- B3 (COTAHIST) ----------------------------------------------------------------------------


def parse_cotahist_line(line: str, wanted: set[str]) -> tuple[str, Point] | None:
    """Linha do COTAHIST (layout fixo da B3, registro 01) → (ticker, (pregão, fechamento)). Só
    o mercado à vista (TPMERC 010) dos tickers pedidos; PREULT tem 2 casas implícitas."""
    if len(line) < 121 or line[0:2] != "01" or line[24:27] != "010":
        return None
    ticker = line[12:24].strip()
    if ticker not in wanted:
        return None
    try:
        day = date(int(line[2:6]), int(line[6:8]), int(line[8:10]))
        close = Decimal(int(line[108:121])) / 100
    except ValueError:
        return None
    return ticker, (day, close)


def _parse_cotahist_zip(fh: Any, wanted: set[str], since: date) -> dict[str, list[Point]]:
    """Lê o zip do COTAHIST (centenas de MB descompactados) linha a linha — numa thread, para não
    travar o event loop da api (o job roda no mesmo processo)."""
    out: dict[str, list[Point]] = defaultdict(list)
    with zipfile.ZipFile(fh) as zf:
        for name in zf.namelist():
            with zf.open(name) as member:
                for raw in member:
                    hit = parse_cotahist_line(raw.decode("latin-1"), wanted)
                    if hit and hit[1][0] >= since:
                        out[hit[0]].append(hit[1])
    return out


async def b3_history(
    tickers: Iterable[str], since: date, client: httpx.AsyncClient
) -> dict[str, list[Point]]:
    """Os fechamentos desde `since` dos tickers, dos COTAHIST anuais de `since.year` até hoje."""
    wanted = set(tickers)
    out: dict[str, list[Point]] = defaultdict(list)
    if not wanted:
        return out
    for year in range(since.year, today_brt().year + 1):
        with tempfile.TemporaryFile() as tmp:
            try:
                async with client.stream(
                    "GET", COTAHIST_URL.format(year=year), timeout=300.0
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes():
                        tmp.write(chunk)
                tmp.seek(0)
                found = await asyncio.to_thread(_parse_cotahist_zip, tmp, wanted, since)
            except (httpx.HTTPError, zipfile.BadZipFile, OSError):
                continue  # o ano que falhar fica de fora; os outros seguem
            for ticker, points in found.items():
                out[ticker].extend(points)
    return out


# ---- Tesouro (CSV do Tesouro Transparente, todas as datas) -----------------------------------


async def treasury_history(
    symbols: Iterable[str], since: date, client: httpx.AsyncClient
) -> dict[str, list[Point]]:
    wanted: dict[tuple[str, int], str] = {}
    for s in symbols:
        parsed = treasury._parse_ticker(s)
        if parsed is not None:
            wanted[parsed] = s
    out: dict[str, list[Point]] = defaultdict(list)
    if not wanted:
        return out
    try:
        async with client.stream("GET", treasury._CSV_URL, timeout=120.0) as resp:
            resp.raise_for_status()
            async for line in treasury._aiter_latin1_lines(resp):
                p = line.split(";")
                if len(p) < 8:
                    continue
                base, venc = treasury._br_date(p[2]), treasury._br_date(p[1])
                if base is None or venc is None:
                    continue
                sym = wanted.get((" ".join(p[0].split()), venc[0]))
                day = date(*base)
                if sym is None or day < since:
                    continue
                pu = treasury._br_float(p[6]) or treasury._br_float(p[7])
                if pu:
                    out[sym].append((day, Decimal(str(pu))))
    except httpx.HTTPError:
        return {}
    return out


# ---- Cripto (CoinGecko market_chart) --------------------------------------------------------


def parse_market_chart(payload: dict[str, Any]) -> list[tuple[date, float]]:
    """`prices: [[ms, preço], ...]` → um preço por dia (UTC; o último do dia)."""
    by_day: dict[date, float] = {}
    for ms, price in payload.get("prices", []):
        by_day[datetime.fromtimestamp(ms / 1000, tz=UTC).date()] = float(price)
    return sorted(by_day.items())


async def crypto_history(
    ids: dict[str, str | None],
    client: httpx.AsyncClient,
    *,
    days: int = 365,
    pause: float = 2.5,
) -> dict[str, list[Point]]:
    """Ticker → preços diários em R$ (ticker sem id do CoinGecko fica de fora)."""
    headers = (
        {"x-cg-demo-api-key": settings.coingecko_api_key} if settings.coingecko_api_key else {}
    )
    out: dict[str, list[Point]] = {}
    for ticker, coin in ids.items():
        if not coin:
            continue
        try:
            resp = await client.get(
                COINGECKO_URL.format(id=coin),
                params={"vs_currency": "brl", "days": days, "interval": "daily"},
                headers=headers,
            )
            resp.raise_for_status()
            out[ticker] = [(d, Decimal(str(p))) for d, p in parse_market_chart(resp.json())]
        except (httpx.HTTPError, ValueError):
            continue
        await asyncio.sleep(pause)  # API gratuita: ~30 chamadas/min
    return out


# ---- gravação e orquestração ----------------------------------------------------------------


async def write_missing(
    conn: asyncpg.Connection, ticker: str, points: list[Point], source: str
) -> int:
    """Grava os dias que faltam no histórico (nunca sobrescreve). Quantos entraram."""
    if not points:
        return 0
    status = await conn.execute(
        "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, is_manual) "
        "SELECT $1, d, p, $2, false FROM unnest($3::date[], $4::numeric[]) AS t(d, p) "
        "ON CONFLICT (ticker, ref_date) DO NOTHING",
        ticker,
        source,
        [d for d, _ in points],
        [p for _, p in points],
    )
    return int(status.split()[-1])


async def held_tickers(conn: asyncpg.Connection) -> dict[str, list[str]]:
    """Os ativos ativos com cotação de mercado, pela fonte: b3, td (Tesouro) e crypto."""
    rows = await conn.fetch(
        "SELECT split_part(key, ':', 1) AS src, price_ref FROM assets "
        "WHERE is_active AND valuation = 'mercado' AND price_ref IS NOT NULL"
    )
    out: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        out[r["src"]].append(r["price_ref"])
    return out


async def run(pool: asyncpg.Pool, *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Uma rodada: um ano de histórico de cada ativo em carteira, só os dias que faltam. A conexão
    do banco só é pega para ler os ativos e para gravar — nunca segura durante os downloads."""
    since = today_brt() - timedelta(days=DAYS)
    async with pool.acquire() as conn:
        held = await held_tickers(conn)
    own = client is None
    http = client or httpx.AsyncClient(follow_redirects=True, timeout=60.0)
    found: dict[str, tuple[str, dict[str, list[Point]]]] = {}
    try:
        found["b3"] = ("b3_cotahist", await b3_history(held.get("b3", []), since, http))
        found["td"] = ("tesouro", await treasury_history(held.get("td", []), since, http))
        ids = {t: settings.coingecko_ids.get(t.upper()) for t in held.get("crypto", [])}
        found["crypto"] = ("coingecko", await crypto_history(ids, http, pause=2.5 if own else 0))
    finally:
        if own:
            await http.aclose()
    stats: dict[str, Any] = {}
    async with pool.acquire() as conn:
        for key, (source, points_by_ticker) in found.items():
            written = 0
            for ticker, points in points_by_ticker.items():
                written += await write_missing(conn, ticker, points, source)
            stats[key] = {
                "symbols": len(held.get(key, [])),
                "fetched": len(points_by_ticker),
                "days_written": written,
            }
    return stats
