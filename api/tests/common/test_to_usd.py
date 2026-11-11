"""v2.2 — cripto em R$ e US$: a conversão fica na API (AD-4)."""

from __future__ import annotations

from decimal import Decimal

from engines.common.money import to_usd
from engines.planning.distribution_service import AssetOut, ClassOut, with_crypto_usd

D = Decimal


def test_to_usd_divides_by_fx_and_rounds_to_cents() -> None:
    assert to_usd(D("1000.00"), D("5.5")) == D("181.82")
    assert to_usd(D("-55.00"), D("5.5")) == D("-10.00")
    assert to_usd(None, D("5.5")) is None
    assert to_usd(D("10"), None) is None
    assert to_usd(D("10"), D("0")) is None


def _cls(cls: str) -> ClassOut:
    asset = AssetOut(
        id="a",
        label="BTC",
        meta=None,
        atual=D(0),
        sugerido=D("550.00"),
        locked=False,
        realizado=D("110.00"),
        pendente=D("440.00"),
    )
    return ClassOut(
        cls=cls,
        label=cls,
        meta=D(10),
        atual=D(9),
        desvio=D(-1),
        banda=D(5),
        floor=D(0),
        sugerido=D("550.00"),
        floor_only=False,
        out_of_band=False,
        locked=False,
        assets=[asset],
        realizado=D("110.00"),
        pendente=D("440.00"),
    )


def test_distribution_crypto_class_gets_usd_lines() -> None:
    classes = with_crypto_usd([_cls("cripto"), _cls("acoes")], D("5.5"))
    crypto, stocks = classes
    assert crypto.usd is not None
    assert (crypto.usd.sugerido, crypto.usd.realizado, crypto.usd.pendente) == (
        D("100.00"),
        D("20.00"),
        D("80.00"),
    )
    assert crypto.assets[0].usd is not None and crypto.assets[0].usd.sugerido == D("100.00")
    assert stocks.usd is None and stocks.assets[0].usd is None
    assert with_crypto_usd([_cls("cripto")], None)[0].usd is None
