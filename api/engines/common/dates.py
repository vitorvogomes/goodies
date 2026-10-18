"""Data 'hoje' ancorada no fuso local (BRT) — débito m4.

Em container a API roda em UTC. `date.today()` cru daria o dia SEGUINTE
entre ~21-24h BRT -> off-by-one nas bordas 7d/30d dos alertas (compute-on-read).
Toda lógica de "hoje" dos alertas deve passar por `today_brt()`.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

_BRT = ZoneInfo("America/Sao_Paulo")


def today_brt(now: datetime | None = None) -> date:
    """Data corrente no fuso America/Sao_Paulo. `now` injetável p/ teste."""
    moment = now or datetime.now(UTC)
    return moment.astimezone(_BRT).date()
