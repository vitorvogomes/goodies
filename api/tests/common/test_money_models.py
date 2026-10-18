"""Story 2.1 — Money/Pct na fronteira HTTP e Valued[T]."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from engines.common.models import Valued
from engines.common.money import Money, Pct, quantize_money


class _Out(BaseModel):
    valor: Money
    taxa: Pct
    total: Valued[Money]


def test_money_and_pct_serialize_as_numbers_with_two_places_half_even() -> None:
    out = _Out(
        valor=Decimal("10.125"),  # HALF_EVEN → 10.12
        taxa=Decimal("55.4850"),  # → 55.48
        total=Valued[Money](value=Decimal("6912.375"), as_of=date(2026, 10, 14), source="live"),
    )
    data = json.loads(out.model_dump_json())
    assert data["valor"] == 10.12 and isinstance(data["valor"], float)
    assert data["taxa"] == 55.48
    assert data["total"] == {
        "value": 6912.38,
        "unavailable_reason": None,
        "as_of": "2026-10-14",
        "source": "live",
        "stale": False,
    }


def test_money_keeps_decimal_in_python() -> None:
    out = _Out(valor=Decimal("1.005"), taxa=Decimal("0"), total=Valued[Money](value=None))
    assert isinstance(out.valor, Decimal)
    assert out.valor == Decimal("1.00")  # quantizado na validação, sem float no meio


def test_money_accepts_strings_and_ints_never_needs_float() -> None:
    out = _Out(valor="68695.66", taxa=12, total=Valued[Money](value="0.004"))
    assert out.valor == Decimal("68695.66") and out.taxa == Decimal("12.00")
    assert out.total.value == Decimal("0.00")


def test_valued_null_carries_reason() -> None:
    v = Valued[Money](value=None, unavailable_reason="sem_receita")
    assert json.loads(v.model_dump_json())["unavailable_reason"] == "sem_receita"


def test_quantize_money_largest_scale() -> None:
    assert quantize_money(Decimal("2.675")) == Decimal("2.68")
    assert quantize_money(Decimal("2.665")) == Decimal("2.66")
