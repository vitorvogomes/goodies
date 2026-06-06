"""Integração do Market Engine (STORY-03-12): worker → Postgres/Redis → endpoints.

Fim-a-fim com fetchers FALSOS (sem rede): roda os corpos dos workers direto e verifica
que os endpoints /market e /portfolio refletem os preços, que o preço manual (RF) fica
intacto, e que API fora vira `stale` (nunca 5xx).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from engines.market.cache import PriceCache
from engines.market.fetchers.base import PriceQuote
from engines.market.service import price_cache_key
from workers.price_workers import run_price_b3, run_price_crypto


class _Fake:
    def __init__(self, prices: dict[str, PriceQuote]) -> None:
        self._p = prices

    async def fetch(self, symbols: Sequence[str]) -> dict[str, PriceQuote]:
        return {s: self._p[s] for s in symbols if s in self._p}


async def _op(pool: Any, uid: str, sym: str, cat: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
            "tipo, quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'Test', $2, $3, 'compra', 10, 5, '2026-01-01')",
            uid,
            sym,
            cat,
        )


async def _cleanup_keys() -> None:
    cache = PriceCache()
    for k in ("b3", "crypto"):
        await cache.delete(price_cache_key(k, "MKT_PETR4"))
        await cache.delete(price_cache_key(k, "MKT_BTC"))


@pytest.mark.asyncio
async def test_worker_to_endpoints_end_to_end(
    api: Any, pool: Any, portfolio_user: dict
) -> None:
    uid, headers = portfolio_user["user_id"], portfolio_user["headers"]
    await _op(pool, uid, "MKT_PETR4", "Ações Nacionais")
    await _op(pool, uid, "MKT_BTC", "Cripto")
    await _op(pool, uid, "MKT_FLASH", "Renda Fixa")
    # preço manual (RF, sem fonte de mercado) via endpoint
    await api.post("/api/v1/market/prices/MKT_FLASH", json={"price_brl": 100.0}, headers=headers)

    # roda os workers com fetchers fake (sem rede)
    await run_price_b3(
        pool,
        brapi=_Fake({"MKT_PETR4": PriceQuote(28.5, None, "brapi")}),
        treasury=_Fake({}),
    )
    await run_price_crypto(
        pool, fetcher=_Fake({"MKT_BTC": PriceQuote(350000.0, 65000.0, "coingecko")})
    )

    try:
        resp = await api.get("/api/v1/market/prices", headers=headers)
        assert resp.status_code == 200
        prices = {p["ticker"]: p for p in resp.json()["prices"]}

        assert prices["MKT_PETR4"]["price_brl"] == 28.5
        assert prices["MKT_PETR4"]["is_manual"] is False
        assert prices["MKT_PETR4"]["stale"] is False
        assert prices["MKT_BTC"]["price_usd"] == 65000.0
        # preço manual intacto (worker não toca RF)
        assert prices["MKT_FLASH"]["price_brl"] == 100.0
        assert prices["MKT_FLASH"]["is_manual"] is True
        assert prices["MKT_FLASH"]["stale"] is False

        # Portfolio passa a valorar com o preço buscado (qtd 10 x 28.5)
        pos = await api.get("/api/v1/portfolio/positions", headers=headers)
        by = {p["asset_symbol"]: p for p in pos.json()}
        assert by["MKT_PETR4"]["valor_atual"] == pytest.approx(285.0)
    finally:
        await _cleanup_keys()


@pytest.mark.asyncio
async def test_external_api_down_yields_stale_not_5xx(
    api: Any, pool: Any, portfolio_user: dict
) -> None:
    uid, headers = portfolio_user["user_id"], portfolio_user["headers"]
    await _op(pool, uid, "MKT_NOQUOTE", "Ações Nacionais")
    # fetcher devolve {} (API fora) → nada atualizado, sem exceção
    stats = await run_price_b3(pool, brapi=_Fake({}), treasury=_Fake({}))
    assert stats["b3"]["updated"] == 0
    assert stats["b3"]["failed"] == stats["b3"]["symbols"]

    resp = await api.get("/api/v1/market/prices", headers=headers)
    assert resp.status_code == 200  # NUNCA 5xx por falha de fonte externa
    p = {x["ticker"]: x for x in resp.json()["prices"]}["MKT_NOQUOTE"]
    assert p["price_brl"] is None
    assert p["stale"] is True
