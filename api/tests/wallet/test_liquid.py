"""LiquidFetcher — L-BTC, client dedicado (ADR-005). STORY-04-04. Mock respx."""
from __future__ import annotations

import httpx
import pytest
import respx

from engines.market.fetchers.wallets.liquid import LiquidFetcher

_LIQUID_BASE = "https://blockstream.info/liquid/api"
_BTC_BASE = "https://blockstream.info/btc/api"
_LBTC = "lbtc-asset-id-placeholder-test"  # asset id real fica no .env (constante pública)


async def _no_sleep(_d: float) -> None: ...


def _fetcher(base: str = _LIQUID_BASE) -> LiquidFetcher:
    return LiquidFetcher(base_url=base, asset_id=_LBTC, address="lq1addr", sleep=_no_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_sums_only_lbtc_utxos() -> None:
    route = respx.get(url__startswith=_LIQUID_BASE).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"value": 10_000_000, "asset": _LBTC},  # 0.1 L-BTC
                {"value": 5_000_000, "asset": _LBTC},  # 0.05 L-BTC
                {"value": 999, "asset": "outro_asset"},  # ignorado (outro asset)
            ],
        )
    )
    out = await _fetcher().fetch()
    assert len(out) == 1
    assert out[0].asset_symbol == "L-BTC"
    assert out[0].quantity == pytest.approx(0.15)  # (10M + 5M) sats / 1e8
    assert out[0].chain == "liquid"
    # ADR-005: caminho /liquid/api/address/{addr}/utxo (NÃO /btc/api)
    path = route.calls.last.request.url.path
    assert path == "/liquid/api/address/lq1addr/utxo"
    assert "/btc/api" not in path


@pytest.mark.asyncio
@respx.mock
async def test_btc_mainchain_shape_yields_nothing_adr005() -> None:
    """ADR-005: apontado p/ /btc/api, os UTXOs Bitcoin (sem `asset`==L-BTC) não contam."""
    respx.get(url__startswith=_BTC_BASE).mock(
        return_value=httpx.Response(
            200,
            json=[{"value": 100_000_000}, {"value": 50_000_000}],  # BTC: sem campo asset
        )
    )
    assert await _fetcher(base=_BTC_BASE).fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_no_lbtc_utxos_returns_empty() -> None:
    respx.get(url__startswith=_LIQUID_BASE).mock(
        return_value=httpx.Response(200, json=[{"value": 123, "asset": "qualquer_outro"}])
    )
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_persistent_error_returns_empty() -> None:
    respx.get(url__startswith=_LIQUID_BASE).mock(return_value=httpx.Response(502))
    assert await _fetcher().fetch() == []


@pytest.mark.asyncio
async def test_no_address_or_asset_is_noop() -> None:
    assert await LiquidFetcher(asset_id=_LBTC, address="", sleep=_no_sleep).fetch() == []
    assert await LiquidFetcher(asset_id="", address="lq1", sleep=_no_sleep).fetch() == []
