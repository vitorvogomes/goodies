"""v2.2 — fatias das pizzas: % do todo a 2 casas, somando 100, do maior ao menor."""

from __future__ import annotations

from decimal import Decimal

from engines.common.shares import pcts, slices

D = Decimal


def test_pcts_sum_exactly_100() -> None:
    out = pcts([D(1), D(1), D(1)])
    assert sum(out) == D("100.00") and sorted(out) == [D("33.33"), D("33.33"), D("33.34")]
    assert pcts([D(0)]) == [D(0)]


def test_slices_sorted_drop_non_positive_and_keep_meta() -> None:
    out = slices([("a", "A", D(10), None), ("b", "B", D(30), D(25)), ("z", "Z", D(0), None)])
    assert [(s.key, s.pct, s.meta) for s in out] == [
        ("b", D("75.00"), D(25)),
        ("a", D("25.00"), None),
    ]
