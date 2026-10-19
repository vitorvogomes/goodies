"""Market Engine — leitura de preço com fallback + cache-aside (STORY-03-07/09/10).

Cadeia de fallback (CLAUDE.md, ADR-004): **Redis → Postgres `asset_prices` → null/stale**.
Nunca levanta (sem HTTP 5xx por falha de fonte externa). É também o write path usado
pelos workers (`cache_aside_write`): grava em Postgres (via `upsert_price`, daqui desde a 3.x,
chokepoint §3.4 com precedência is_manual) e popula o Redis com a chave `price:{tipo}:{ticker}`.

`tipo` (b3/crypto/tesouro) deriva da categoria canônica do ativo (`constants` frozensets);
Renda Fixa & afins não têm fonte de mercado → `tipo=None` (preço sempre is_manual).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from config import settings
from engines.common.assets import (
    B3_CATEGORIES,
    CRYPTO_CATEGORIES,
    TREASURY_CATEGORIES,
)
from engines.common.cache import cache
from engines.common.dates import today_brt
from engines.common.models import Valued

_TTL_BY_TYPE = {
    "b3": settings.ttl_b3,
    "crypto": settings.ttl_crypto,
    "tesouro": settings.ttl_tesouro,
}


def cache_type_for_category(category: str | None) -> str | None:
    """Categoria canônica -> tipo de cache/fetcher. None = sem fonte de mercado (is_manual)."""
    if category in B3_CATEGORIES:
        return "b3"
    if category in CRYPTO_CATEGORIES:
        return "crypto"
    if category in TREASURY_CATEGORIES:
        return "tesouro"
    return None


async def lacks_market_source(conn: asyncpg.Connection, ticker: str) -> bool:
    """True se o ticker é de categoria SEM fetcher (Renda Fixa/caixinha/CDB/Flash).

    Para esses o preço é sempre manual: liberar o is_manual o deixaria stale para sempre.
    Ticker sem operação (ex.: só em carteira cripto) não é bloqueado — tem fonte.
    """
    category = await conn.fetchval(
        "SELECT asset_category FROM asset_operations WHERE asset_symbol = $1 LIMIT 1",
        ticker,
    )
    return category is not None and cache_type_for_category(category) is None


_COMPUTED = ("cdi", "taxa")  # renda fixa valorada pelo app: também não aceita preço digitado


async def has_market_source(conn: asyncpg.Connection, ticker: str) -> bool:
    """Story 10.2: o ativo tem preço automático — e então não aceita preço manual. Tem quando a
    classe das operações tem fetcher (B3, Tesouro, cripto), quando o ativo é valorado pelo app
    (CDI, taxa) ou quando já há preço automático gravado; `valuation = 'manual'` nunca tem."""
    valuation = await conn.fetchval("SELECT valuation FROM assets WHERE price_ref = $1", ticker)
    if valuation == "manual":
        return False
    if valuation in _COMPUTED:
        return True
    category = await conn.fetchval(
        "SELECT asset_category FROM asset_operations WHERE asset_symbol = $1 LIMIT 1", ticker
    )
    if category is not None and cache_type_for_category(category) is not None:
        return True
    automatic = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM asset_prices WHERE ticker = $1 AND NOT is_manual "
        "AND source <> 'manual')",
        ticker,
    )
    return bool(automatic)


# source gravado em asset_prices -> tipo (p/ calcular staleness na leitura via Postgres).
_TYPE_BY_SOURCE = {"brapi": "b3", "b3": "b3", "coingecko": "crypto", "tesouro": "tesouro"}


def price_cache_key(cache_type: str, ticker: str) -> str:
    return f"price:{cache_type}:{ticker}"


async def invalidate_price_cache(ticker: str) -> None:
    """Remove o ticker do cache Redis após uma escrita manual (manual sempre vence).

    O preço manual é gravado no Postgres, mas a leitura (`get_price`) consulta o Redis
    primeiro pela `cache_type` da categoria — sem isto, um preço de mercado cacheado
    mascararia o override manual em `/market` por até o TTL. Apaga as 3 chaves candidatas
    (só uma existe); fail-soft.
    """
    for cache_type in ("b3", "crypto", "tesouro"):
        await cache().delete(price_cache_key(cache_type, ticker))


def _is_stale(is_manual: bool, source: str, fetched_at: datetime, now: datetime) -> bool:
    """Manual nunca envelhece (autoritativo); de mercado, envelhece após o TTL do tipo."""
    if is_manual:
        return False
    ttl = _TTL_BY_TYPE.get(_TYPE_BY_SOURCE.get(source, ""), settings.ttl_b3)
    return (now - fetched_at).total_seconds() > ttl


def _missing(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "price_brl": None,
        "price_usd": None,
        "source": None,
        "is_manual": False,
        "stale": True,
        "last_updated": None,
    }


def _from_cache_hit(ticker: str, hit: dict[str, Any]) -> dict[str, Any]:
    """Preço a partir de um hit no Redis: presente ⇒ dentro do TTL ⇒ fresco."""
    return {
        "ticker": ticker,
        "price_brl": hit.get("price_brl"),
        "price_usd": hit.get("price_usd"),
        "source": hit.get("source"),
        "is_manual": False,
        "stale": False,
        "last_updated": hit.get("fetched_at"),
    }


def _from_pg_row(ticker: str, row: Any, now: datetime) -> dict[str, Any]:
    """Preço a partir de uma linha de asset_prices (staleness por TTL/is_manual)."""
    fetched_at: datetime = row["fetched_at"]
    return {
        "ticker": ticker,
        "price_brl": float(row["price_brl"]),
        "price_usd": float(row["price_usd"]) if row["price_usd"] is not None else None,
        "source": row["source"],
        "is_manual": row["is_manual"],
        "stale": _is_stale(row["is_manual"], row["source"], fetched_at, now),
        "last_updated": fetched_at.isoformat(),
    }


async def get_price(
    conn: asyncpg.Connection,
    ticker: str,
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Preço corrente do ticker pela cadeia Redis → Postgres → null/stale. Nunca levanta."""
    now = now or datetime.now(tz=UTC)
    cache_type = cache_type_for_category(category)
    if cache_type is not None:
        hit = await cache().get(price_cache_key(cache_type, ticker))
        if hit is not None:
            return _from_cache_hit(ticker, hit)

    row = await conn.fetchrow(
        "SELECT price_brl, price_usd, source, is_manual, fetched_at "
        "FROM asset_prices WHERE ticker = $1",
        ticker,
    )
    if row is None:
        return _missing(ticker)
    return _from_pg_row(ticker, row, now)


async def list_user_prices(
    conn: asyncpg.Connection, user_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Preço corrente de todos os tickers do usuário (mesma cadeia de fallback do
    `get_price`, mas em LOTE: 1 SELECT `ticker = ANY($1)` + 1 Redis MGET, em vez de
    N idas por ticker). A carteira cresce no m4 (cripto/wallets) → evita o N+1 (§debito m3 #2).
    """
    now = now or datetime.now(tz=UTC)
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol, asset_category FROM asset_operations "
        "WHERE user_id = $1 ORDER BY asset_symbol",
        user_id,
    )
    if not rows:
        return []
    tickers = [r["asset_symbol"] for r in rows]
    category_of = {r["asset_symbol"]: r["asset_category"] for r in rows}

    # 1 SELECT em lote (substitui o fetchrow por ticker do get_price)
    pg = {
        r["ticker"]: r
        for r in await conn.fetch(
            "SELECT ticker, price_brl, price_usd, source, is_manual, fetched_at "
            "FROM asset_prices WHERE ticker = ANY($1)",
            tickers,
        )
    }
    # 1 Redis MGET só nos tickers com fonte de mercado (cache_type != None)
    typed = [
        (t, ct) for t in tickers if (ct := cache_type_for_category(category_of[t])) is not None
    ]
    hits = await cache().mget([price_cache_key(ct, t) for t, ct in typed])
    cached = {t: v for (t, _ct), v in zip(typed, hits, strict=True) if v is not None}

    out: list[dict[str, Any]] = []
    for ticker in tickers:
        hit = cached.get(ticker)
        if hit is not None:
            out.append(_from_cache_hit(ticker, hit))
        elif (row := pg.get(ticker)) is not None:
            out.append(_from_pg_row(ticker, row, now))
        else:
            out.append(_missing(ticker))
    return out


async def prices_for_tickers(
    conn: asyncpg.Connection,
    tickers: Sequence[str],
    *,
    category: str | None = None,
    now: datetime | None = None,
) -> dict[str, tuple[float | None, float | None]]:
    """Preço (BRL, USD) por ticker em LOTE pela cadeia Redis→Postgres (cache-aside do m3).

    Valoração de wallet/DeFi: todos cripto → `category='Cripto'` usa o cache cripto (em vez
    de bater só no Postgres). Reusa as chaves/builders do m3; sem N+1 e sem SELECT de preço
    duplicado fora desta engine. Ticker ausente NÃO entra no dict (call site faz
    `.get(sym, (None, None))`).
    """
    keys = list(dict.fromkeys(tickers))  # dedup preservando ordem
    if not keys:
        return {}
    now = now or datetime.now(tz=UTC)
    cache_type = cache_type_for_category(category)

    pg = {
        r["ticker"]: r
        for r in await conn.fetch(
            "SELECT ticker, price_brl, price_usd FROM asset_prices WHERE ticker = ANY($1)",
            keys,
        )
    }
    cached: dict[str, Any] = {}
    if cache_type is not None:
        hits = await cache().mget([price_cache_key(cache_type, t) for t in keys])
        cached = {t: v for t, v in zip(keys, hits, strict=True) if v is not None}

    out: dict[str, tuple[float | None, float | None]] = {}
    for t in keys:
        hit = cached.get(t)
        if hit is not None:
            out[t] = (hit.get("price_brl"), hit.get("price_usd"))
        elif (row := pg.get(t)) is not None:
            out[t] = (
                float(row["price_brl"]) if row["price_brl"] is not None else None,
                float(row["price_usd"]) if row["price_usd"] is not None else None,
            )
    return out


async def cache_aside_write(
    conn: asyncpg.Connection,
    ticker: str,
    *,
    cache_type: str,
    price_brl: float,
    price_usd: float | None,
    source: str,
    ttl: int,
) -> bool:
    """Grava um preço de mercado: Postgres (chokepoint) + Redis. Usado pelos workers.

    Respeita a precedência is_manual (a escrita em Postgres é ignorada sobre linha
    manual); nesse caso NÃO popula o Redis (não contradiz o preço manual). Retorna
    True se gravou, False se foi ignorado.
    """
    written = await upsert_price(
        conn, ticker, price_brl, price_usd=price_usd, source=source, is_manual=False
    )
    if not written:
        return False
    await cache().set(
        price_cache_key(cache_type, ticker),
        {
            "price_brl": price_brl,
            "price_usd": price_usd,
            "source": source,
            "fetched_at": written["fetched_at"].isoformat(),
        },
        ttl,
    )
    return True


# --------------------------------------------------------------------------------------------
# Escrita de preço: chokepoint único (ADR-012), em `market` desde o Épico 3 (AD-1). Quem deriva do
# preço (o XIRR do portfolio) registra `on_price_changed` em `main.py`.
# --------------------------------------------------------------------------------------------

PriceHook = Callable[[asyncpg.Connection, str], Awaitable[None]]
_price_hooks: list[PriceHook] = []


def register_on_price_changed(hook: PriceHook) -> None:
    if hook not in _price_hooks:
        _price_hooks.append(hook)


async def _price_changed(conn: asyncpg.Connection, ticker: str) -> None:
    for hook in _price_hooks:
        await hook(conn, ticker)


async def upsert_price(
    conn: asyncpg.Connection,
    ticker: str,
    price_brl: float | Decimal,
    *,
    price_usd: float | None = None,
    source: str = "manual",
    is_manual: bool = True,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Chokepoint único de escrita de preço (PUT manual + worker do Market Engine).

    `as_of`: a data do preço quando não é agora (ex.: o consolidado B3 de 30/09) — vira o
    `fetched_at` e o dia do histórico, para o Carimbo de data não chamar de hoje um preço antigo.

    Precedência is_manual (§3.4): uma escrita do worker (`is_manual=False`) NUNCA
    sobrescreve uma linha manual (`is_manual=True`) — preços sem fonte de mercado
    (Flash/RF/caixinhas/DeFi). Uma escrita manual sempre vence. Quando a gravação
    de fato ocorre, invalida o cache de XIRR de todos os usuários que detêm o ticker
    (ADR-008) — o worker chama esta função direto, sem passar pelo router.

    `price_usd` é opcional (só CoinGecko fornece). Retorna a linha gravada, ou `{}`
    quando a escrita foi ignorada pela precedência is_manual.
    """
    # CTE `prev` lê o preço anterior no mesmo statement (snapshot do início) p/ só
    # invalidar o XIRR quando price_brl/price_usd realmente mudar (§debito m3 #3).
    row = await conn.fetchrow(
        """
        WITH prev AS (SELECT price_brl, price_usd FROM asset_prices WHERE ticker = $1)
        INSERT INTO asset_prices (ticker, price_brl, price_usd, source, is_manual, fetched_at)
        VALUES ($1, $2, $3, $4, $5, COALESCE($6, now()))
        ON CONFLICT (ticker) DO UPDATE
          SET price_brl = EXCLUDED.price_brl,
              -- só sobrescreve USD quando um novo é fornecido (manual BRL não apaga o USD)
              price_usd = COALESCE(EXCLUDED.price_usd, asset_prices.price_usd),
              source = EXCLUDED.source,
              is_manual = EXCLUDED.is_manual,
              fetched_at = EXCLUDED.fetched_at
          WHERE asset_prices.is_manual = false OR EXCLUDED.is_manual = true
        RETURNING ticker, price_brl, price_usd, source, is_manual, fetched_at,
                  (SELECT price_brl FROM prev) AS prev_brl,
                  (SELECT price_usd FROM prev) AS prev_usd
        """,
        ticker,
        price_brl,
        price_usd,
        source,
        is_manual,
        as_of,
    )
    if row is None:
        return {}  # escrita ignorada pela precedência is_manual
    # XIRR é em BRL: só invalidar quando price_brl muda (mudança só de USD não afeta o XIRR).
    # Comparação exata em Decimal (já arredondado pelo numeric); linha nova → prev None → mudou.
    brl_changed = row["prev_brl"] is None or row["price_brl"] != row["prev_brl"]
    if brl_changed:
        await _price_changed(conn, ticker)
    cols = ("ticker", "price_brl", "price_usd", "source", "is_manual", "fetched_at")
    return {k: row[k] for k in cols}


async def clear_manual_price(conn: asyncpg.Connection, ticker: str) -> bool:
    """Libera um preço manual p/ o worker voltar a sobrescrever (is_manual=false).

    NÃO apaga o preço — só limpa a flag (ação explícita do usuário, ADR-012 intacto).
    Invalida o cache de XIRR de quem detém o ticker (o preço pode mudar no próximo scan).
    Devolve False se o ticker não existe (o router responde 404). Idempotente.
    """
    updated = await conn.execute(
        "UPDATE asset_prices SET is_manual = false WHERE ticker = $1", ticker
    )
    if updated == "UPDATE 0":
        return False
    await _price_changed(conn, ticker)
    return True


# --------------------------------------------------------------------------------------------
# Fonte automática do Painel (Story 4.2): até quando os índices estão atualizados
# --------------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------------
# Histórico de CDI e IPCA (Story 7.2 — AD-1: o SQL de `benchmark_data` mora aqui)
# --------------------------------------------------------------------------------------------

BENCHMARK_START = date(2024, 6, 1)  # o backfill cobre desde jun/2024
_CATCHUP_OVERLAP = timedelta(days=40)  # refaz um pouco antes: revisão do BCB e IPCA mensal


def benchmark_catchup_start(last: date | None) -> date:
    """De onde o catch-up busca: um pouco antes do último ponto (idempotente), ou o início."""
    if last is None:
        return BENCHMARK_START
    return max(BENCHMARK_START, last - _CATCHUP_OVERLAP)


async def benchmark_last_date(conn: asyncpg.Connection) -> date | None:
    """O último dia gravado da série mais atrasada (o IPCA sai depois do mês). Série sem nenhum
    ponto → None (o catch-up volta ao início), senão a série vazia nunca seria buscada."""
    value: date | None = await conn.fetchval(
        "SELECT CASE WHEN count(d) < 2 THEN NULL ELSE min(d) END FROM (SELECT max(b.ref_date) AS d "
        "FROM (VALUES ('CDI'), ('IPCA')) s(series) LEFT JOIN benchmark_data b "
        "ON b.series = s.series GROUP BY s.series) x"
    )
    return value


async def upsert_benchmarks(conn: asyncpg.Connection, points: Sequence[Any]) -> int:
    """Grava pontos de benchmark (idempotente por série e data)."""
    await conn.executemany(
        """
        INSERT INTO benchmark_data (series, ref_date, value, source)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (series, ref_date) DO UPDATE
          SET value = EXCLUDED.value, source = EXCLUDED.source, fetched_at = now()
        """,
        [(p.series, p.ref_date, p.value, p.source) for p in points],
    )
    return len(points)


async def cdi_daily(conn: asyncpg.Connection, start: date, end: date) -> list[tuple[date, Decimal]]:
    """CDI diário (% ao dia) de cada dia útil publicado entre as datas."""
    rows = await conn.fetch(
        "SELECT ref_date, value FROM benchmark_data WHERE series = 'CDI' "
        "AND ref_date BETWEEN $1 AND $2 ORDER BY ref_date",
        start,
        end,
    )
    return [(r["ref_date"], Decimal(str(r["value"]))) for r in rows]


async def ipca_monthly(conn: asyncpg.Connection, start: date, end: date) -> dict[date, Decimal]:
    """IPCA mensal (% no mês), chave = 1º dia do mês."""
    rows = await conn.fetch(
        "SELECT ref_date, value FROM benchmark_data WHERE series = 'IPCA' "
        "AND ref_date BETWEEN $1 AND $2 ORDER BY ref_date",
        start,
        end,
    )
    return {r["ref_date"].replace(day=1): Decimal(str(r["value"])) for r in rows}


async def latest_index_date(conn: asyncpg.Connection) -> Any:
    """Último dia com CDI publicado (o IPCA é mensal e sai depois)."""
    return await conn.fetchval("SELECT max(ref_date) FROM benchmark_data WHERE series = 'CDI'")


async def prices_as_of(
    conn: asyncpg.Connection, tickers: list[str], day: date
) -> dict[str, Valued[Decimal]]:
    """`price_as_of` de vários tickers numa consulta só (sem preço até `day` → `sem_preco`)."""
    rows = await conn.fetch(
        "SELECT DISTINCT ON (ticker) ticker, ref_date, price_brl, source FROM asset_price_history "
        "WHERE ticker = ANY($1::text[]) AND ref_date <= $2 ORDER BY ticker, ref_date DESC",
        list(set(tickers)),
        day,
    )
    found = {
        r["ticker"]: Valued[Decimal](value=r["price_brl"], as_of=r["ref_date"], source=r["source"])
        for r in rows
    }
    return {t: found.get(t, Valued[Decimal](unavailable_reason="sem_preco")) for t in tickers}


async def price_as_of(conn: asyncpg.Connection, ticker: str, day: date) -> Valued[Decimal]:
    """Preço de `ticker` até `day` (Story 5.1, AD-8): o último do histórico com data ≤ `day`. Sem
    nenhum, `Valued` nulo com `sem_preco` — nunca o preço de hoje para um mês passado."""
    row = await conn.fetchrow(
        "SELECT ref_date, price_brl, source FROM asset_price_history "
        "WHERE ticker = $1 AND ref_date <= $2 ORDER BY ref_date DESC LIMIT 1",
        ticker,
        day,
    )
    if row is None:
        return Valued[Decimal](unavailable_reason="sem_preco")
    return Valued[Decimal](value=row["price_brl"], as_of=row["ref_date"], source=row["source"])


# --------------------------------------------------------------------------------------------
# Preço manual em dólar: o token cripto sem cotação se informa em US$
# --------------------------------------------------------------------------------------------

MANUAL_USD = "manual_usd"  # `source` do preço manual informado em dólar


async def usd_brl(conn: asyncpg.Connection) -> Decimal | None:
    """A cotação do dólar das carteiras: R$ ÷ US$ do USDT (ou do USDC) do CoinGecko."""
    row = await conn.fetchrow(
        "SELECT price_brl / price_usd AS fx FROM asset_prices WHERE ticker IN ('USDT', 'USDC') "
        "AND NOT is_manual AND price_usd > 0 ORDER BY (ticker = 'USDT') DESC, fetched_at DESC "
        "LIMIT 1"
    )
    return Decimal(row["fx"]) if row is not None else None


async def set_manual_usd(
    conn: asyncpg.Connection, ticker: str, price_usd: Decimal, *, as_of: datetime | None = None
) -> dict[str, Any] | None:
    """Grava o preço manual em US$ e o R$ pela cotação de agora; sem cotação → None."""
    fx = await usd_brl(conn)
    if fx is None:
        return None
    return await upsert_price(
        conn,
        ticker,
        (price_usd * fx).quantize(Decimal("0.00000001")),
        price_usd=float(price_usd),
        source=MANUAL_USD,
        is_manual=True,
        as_of=as_of,
    )


_HISTORY_OF_DAY = (
    "SELECT ref_date, price_brl, price_usd FROM asset_price_history "
    "WHERE ticker = $1 AND ref_date = ($2::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date"
)


async def refresh_manual_usd(conn: asyncpg.Connection) -> int:
    """Refaz o R$ dos preços manuais em dólar pela cotação atual (a data informada fica). Roda
    depois do preço cripto. O histórico guarda cada dia com a cotação do dia: o dia informado
    fica como estava e o R$ novo vale a partir de hoje. Quantos foram refeitos."""
    fx = await usd_brl(conn)
    if fx is None:
        return 0
    rows = await conn.fetch(
        "SELECT ticker, price_usd, fetched_at FROM asset_prices "
        "WHERE is_manual AND source = $1 AND price_usd IS NOT NULL",
        MANUAL_USD,
    )
    today = today_brt()
    async with conn.transaction():
        for r in rows:
            informed = await conn.fetchrow(_HISTORY_OF_DAY, r["ticker"], r["fetched_at"])
            brl = (Decimal(r["price_usd"]) * fx).quantize(Decimal("0.00000001"))
            await upsert_price(
                conn,
                r["ticker"],
                brl,
                price_usd=float(r["price_usd"]),
                source=MANUAL_USD,
                is_manual=True,
                as_of=r["fetched_at"],
            )
            # O trigger regravou o dia informado com a cotação de agora: ele volta ao que era.
            if informed is not None:
                await conn.execute(
                    "UPDATE asset_price_history SET price_brl = $3, price_usd = $4 "
                    "WHERE ticker = $1 AND ref_date = $2",
                    r["ticker"],
                    informed["ref_date"],
                    informed["price_brl"],
                    informed["price_usd"],
                )
            await conn.execute(
                "INSERT INTO asset_price_history "
                "(ticker, ref_date, price_brl, price_usd, source, is_manual) "
                "VALUES ($1, $2, $3, $4, $5, true) ON CONFLICT (ticker, ref_date) DO UPDATE SET "
                "price_brl = EXCLUDED.price_brl, price_usd = EXCLUDED.price_usd, "
                "source = EXCLUDED.source, is_manual = EXCLUDED.is_manual",
                r["ticker"],
                today,
                brl,
                r["price_usd"],
                MANUAL_USD,
            )
    return len(rows)
