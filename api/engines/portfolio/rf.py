"""Renda fixa pelo CDI real (Story 7.4 — FR-23): o valor de caixinhas e CDBs com %CDI cadastrado
no ativo (`assets.valuation = 'cdi'`, `assets.pct_cdi`) sobre o CDI diário publicado pelo BCB
(`benchmark_data`, Story 7.2) — nunca uma taxa fixa (`settings.cdi_anual` não entra).

Cada aporte rende Π(1 + CDI do dia × %CDI) pelos dias úteis de CDI publicado desde a data dele até a
data pedida; o resgate sai pelo valor que renderia (a aproximação de sempre, desprezível com pouco
resgate). Depois do último CDI publicado não rende — o "CDI até". Dia útil (seg–sex) sem CDI
publicado no meio do caminho usa o CDI publicado mais próximo e o valor sai `estimated`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from . import calc

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class CdiValue:
    value: Decimal
    cdi_until: date | None  # último dia de CDI publicado usado
    estimated: bool  # algum dia útil sem CDI publicado (ou nenhum CDI)
    estimated_share: float = 0.0  # fração dos dias úteis sem CDI publicado (0 a 1)


def _business_days(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _daily_rates(
    first: date, until: date, cdi: Sequence[tuple[date, Decimal]]
) -> tuple[dict[date, Decimal], int]:
    """Taxa (% a.d.) de cada dia útil de `first` a `until`: a publicada ou a mais próxima; e quantos
    dias foram estimados."""
    published = dict(cdi)
    known = sorted(published)
    rates: dict[date, Decimal] = {}
    estimated = 0
    for d in _business_days(first, until):
        if d in published:
            rates[d] = published[d]
            continue
        estimated += 1
        nearest = min(known, key=lambda k: (abs((k - d).days), k))
        rates[d] = published[nearest]
    for d in known:  # dia publicado fora de seg–sex (não deveria) também conta
        if first <= d <= until:
            rates[d] = published[d]
    return rates, estimated


def cdi_value(
    ops: Iterable[Mapping[str, Any]],
    as_of: date,
    pct_cdi: Decimal,
    cdi: Sequence[tuple[date, Decimal]],
) -> CdiValue:
    ops = [op for op in ops if op["data_operacao"] <= as_of]
    published = [(d, r) for d, r in cdi if d < as_of]
    until = max((d for d, _ in published), default=None)
    if until is None or not ops:
        value = calc.net_contributed(ops)
        return CdiValue(value.quantize(_CENT), None, bool(ops), 1.0 if ops else 0.0)
    first = min(op["data_operacao"] for op in ops)
    rates, estimated = _daily_rates(first, until, published)
    days = sorted(rates)
    total = Decimal(0)
    for op in ops:
        if op["tipo"] not in calc.INFLOW and op["tipo"] not in calc.OUTFLOW:
            continue
        factor = Decimal(1)
        for d in days:
            if d >= op["data_operacao"]:
                factor *= 1 + rates[d] * pct_cdi / 100 / 100
        amount = Decimal(str(op["quantidade"])) * Decimal(str(op["valor_unitario"]))
        total += amount * factor if op["tipo"] in calc.INFLOW else -amount * factor
    share = estimated / len(days) if days else 0.0
    return CdiValue(total.quantize(_CENT), until, estimated > 0, share)


async def rf_cdi_assets(conn: Any) -> dict[str, Decimal]:
    """Símbolo (`price_ref`) → %CDI dos ativos valorados pelo CDI (`assets.valuation = 'cdi'`)."""
    rows = await conn.fetch(
        "SELECT price_ref, pct_cdi FROM assets WHERE valuation = 'cdi' AND pct_cdi IS NOT NULL"
    )
    return {r["price_ref"]: Decimal(r["pct_cdi"]) for r in rows}


# --------------------------------------------------------------------------------------------
# Debênture pela taxa cadastrada (Story 7.6 — files/debentures-flash/formula.md)
# --------------------------------------------------------------------------------------------


def pre_value(ops: Iterable[Mapping[str, Any]], as_of: date, monthly_factor: Decimal) -> Decimal:
    """Pré-fixado da Flash: cada aporte × (1 + fator mensal/100)^(dias corridos/30) até a data; o
    resgate (cupom, vencimento) sai pelo valor que renderia — a mesma aproximação da caixinha."""
    total = Decimal(0)
    base = 1 + float(monthly_factor) / 100
    for op in ops:
        d = op["data_operacao"]
        if d > as_of or (op["tipo"] not in calc.INFLOW and op["tipo"] not in calc.OUTFLOW):
            continue
        amount = Decimal(str(op["quantidade"])) * Decimal(str(op["valor_unitario"]))
        factor = Decimal(repr(base ** ((as_of - d).days / 30)))
        total += amount * factor if op["tipo"] in calc.INFLOW else -amount * factor
    return total.quantize(_CENT)


async def rf_rate_assets(conn: Any) -> dict[str, Decimal]:
    """Símbolo (`price_ref`) → fator mensal (% a.m.) das debêntures (`valuation = 'taxa'`)."""
    rows = await conn.fetch(
        "SELECT a.price_ref, d.monthly_factor FROM assets a "
        "JOIN debentures d ON d.asset_id = a.id WHERE a.valuation = 'taxa'"
    )
    return {r["price_ref"]: Decimal(r["monthly_factor"]) for r in rows}
