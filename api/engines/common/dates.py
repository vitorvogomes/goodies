"""Data 'hoje' ancorada no fuso local (BRT) — débito m4.

Em container a API roda em UTC. `date.today()` cru daria o dia SEGUINTE
entre ~21-24h BRT -> off-by-one nas bordas 7d/30d dos alertas (compute-on-read).
Toda lógica de "hoje" dos alertas deve passar por `today_brt()`.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

_BRT = ZoneInfo("America/Sao_Paulo")


def today_brt(now: datetime | None = None) -> date:
    """Data corrente no fuso America/Sao_Paulo. `now` injetável p/ teste."""
    moment = now or datetime.now(UTC)
    return moment.astimezone(_BRT).date()


# ---------------------------------------------------------------- período (AD-14 — Story 2.1)

MIN_MONTH = date(2024, 7, 1)  # início da base (jul/2024); nenhum período antes disso
LEITURAS = ("mes", "tri", "ano", "inicio")
_PERIODO_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def parse_periodo(periodo: str) -> date:
    """`"2026-10"` → `date(2026, 10, 1)` (mês no banco = date no dia 1)."""
    m = _PERIODO_RE.match(periodo or "")
    if m is None:
        raise ValueError(f"periodo inválido: {periodo!r} (esperado YYYY-MM)")
    return date(int(m[1]), int(m[2]), 1)


def add_months(d: date, n: int) -> date:
    """1º dia do mês `n` meses depois (ou antes, com `n` negativo) do mês de `d`."""
    index = d.year * 12 + d.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def month_end(month: date) -> date:
    """Último dia do mês de `month`."""
    return add_months(month, 1) - timedelta(days=1)


def months_between(start: date, end: date) -> list[date]:
    """Os meses de `start` até `end` (inclusive), em ordem."""
    out: list[date] = []
    month = start.replace(day=1)
    while month <= end:
        out.append(month)
        month = add_months(month, 1)
    return out


def resolve_period(periodo: str, leitura: str) -> list[date]:
    """Meses da leitura ancorada no período, nunca depois dele nem antes de jul/2024 (igual a
    `web/lib/period.ts`): tri = trimestre civil até o período; ano = jan até o período; inicio =
    jul/2024 até o período."""
    if leitura not in LEITURAS:
        raise ValueError(f"leitura inválida: {leitura!r} (mes, tri, ano, inicio)")
    end = parse_periodo(periodo)
    start = {
        "mes": end,
        "tri": date(end.year, (end.month - 1) // 3 * 3 + 1, 1),
        "ano": date(end.year, 1, 1),
        "inicio": MIN_MONTH,
    }[leitura]
    start = max(start, MIN_MONTH)
    months: list[date] = []
    while start <= end:
        months.append(start)
        start = add_months(start, 1)
    return months


_MONTHS_PT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def month_label(month: date) -> str:
    """`date(2026, 10, 1)` → "out/2026" (rótulo de mês das mensagens)."""
    return f"{_MONTHS_PT[month.month - 1]}/{month.year}"
