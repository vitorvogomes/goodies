"""Cobertura das fontes de arquivo (FR-3/FR-4 — Story 3.9): atualizado até, atraso e lacunas.
Funções puras sobre os períodos de `import_batch_files` (lotes `applied` e `legacy`)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

# Ordem e rótulos do Bloco Fontes (fontes de arquivo).
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("nubank_pf", "Nubank PF", "OFX ou CSV"),
    ("nubank_mei", "Nubank MEI", "OFX ou CSV"),
    ("b3_movimentacao", "B3 movimentação", "xlsx"),
    ("b3_negociacao", "B3 negociação", "xlsx"),
    ("b3_consolidado", "B3 consolidado", "xlsx"),
)
PF_LIMIT_DAYS = 7


@dataclass(frozen=True)
class Coverage:
    start: date
    end: date


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def required_until(today: date) -> date:
    """Mês anterior coberto até o dia 15: depois do dia 15, o fim do mês anterior; até lá, o fim do
    mês retrasado."""
    first = today.replace(day=1)
    previous_end = first - timedelta(days=1)
    if today.day > 15:
        return previous_end
    return previous_end.replace(day=1) - timedelta(days=1)


def is_stale(key: str, until: date | None, today: date) -> bool:
    if until is None:
        return False
    if key == "nubank_pf":
        return (today - until).days > PF_LIMIT_DAYS
    if key in ("nubank_mei", "b3_consolidado"):
        return until < required_until(today)
    return False  # movimentação/negociação: só o aviso de transferência não coberta


def _merged(coverage: list[Coverage]) -> list[Coverage]:
    merged: list[Coverage] = []
    for c in sorted(coverage, key=lambda c: (c.start, c.end)):
        if merged and c.start <= merged[-1].end + timedelta(days=1):
            last = merged[-1]
            merged[-1] = Coverage(last.start, max(last.end, c.end))
        else:
            merged.append(c)
    return merged


def interval_gaps(coverage: list[Coverage]) -> list[tuple[date, date]]:
    """Dias sem arquivo entre o primeiro e o último import (Nubank)."""
    merged = _merged(coverage)
    return [(a.end + timedelta(days=1), b.start - timedelta(days=1)) for a, b in pairwise(merged)]


def consolidado_gaps(coverage: list[Coverage]) -> list[tuple[date, date]]:
    """Meses sem consolidado entre o primeiro e o último (o anual cobre o ano)."""
    if not coverage:
        return []
    covered: set[tuple[int, int]] = set()
    for c in coverage:
        y, m = c.start.year, c.start.month
        while (y, m) <= (c.end.year, c.end.month):
            covered.add((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    first, last = min(covered), max(covered)
    gaps: list[tuple[date, date]] = []
    y, m = first
    while (y, m) <= last:
        if (y, m) not in covered:
            start = date(y, m, 1)
            gaps.append((start, _month_end(start)))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return gaps
