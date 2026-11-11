"""Fatias de um todo (v2.2 — gráficos de pizza): cada item com o % do total, a 2 casas, pelo maior
resto para somarem 100,00 exatos. Itens sem valor positivo ficam de fora; ordem do maior ao menor.
A conta fica na API (AD-4): o front só desenha."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_FLOOR, Decimal

from pydantic import BaseModel

from engines.common.money import Money, Pct


class Slice(BaseModel):
    key: str
    label: str
    value: Money
    pct: Pct  # % do todo
    meta: Pct | None = None  # a meta do item, quando houver (anel da meta na carteira)


def pcts(values: list[Decimal]) -> list[Decimal]:
    """% de cada valor no total, 2 casas, somando 100,00 (maior resto)."""
    total = sum(values, Decimal(0))
    if total <= 0:
        return [Decimal(0) for _ in values]
    raw = [v * 10000 / total for v in values]
    floors = [r.to_integral_value(rounding=ROUND_FLOOR) for r in raw]
    left = int(10000 - sum(floors))
    for i in sorted(range(len(values)), key=lambda i: -(raw[i] - floors[i]))[:left]:
        floors[i] += 1
    return [(f / 100).quantize(Decimal("0.01")) for f in floors]


def slices(items: Iterable[tuple[str, str, Decimal, Decimal | None]]) -> list[Slice]:
    """(chave, rótulo, valor, meta) → fatias com o %; sem valor positivo, fora."""
    kept = sorted((i for i in items if i[2] > 0), key=lambda i: -i[2])
    return [
        Slice(key=k, label=label, value=v, pct=p, meta=meta)
        for (k, label, v, meta), p in zip(kept, pcts([i[2] for i in kept]), strict=True)
    ]
