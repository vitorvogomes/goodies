"""Central de avisos (AD-10 — Story 3.1): junta os providers registrados na leitura.

Ordem: divergências antes de avisos; dentro de cada uma, mais recentes primeiro. Dispensa esconde o
aviso enquanto o fingerprint for o mesmo; quando o provider para de emitir a key, a dispensa some.
"""

from __future__ import annotations

from datetime import date

import asyncpg

from engines.common.alerts import Alert, AlertContext, AlertProvider
from engines.common.dates import today_brt
from engines.common.month_status import month_status
from engines.common.owner import get_owner_id

from . import queries
from .models import AlertList

_providers: list[AlertProvider] = []


def register_alert_provider(provider: AlertProvider) -> None:
    if provider not in _providers:
        _providers.append(provider)


def unregister_alert_provider(provider: AlertProvider) -> None:
    if provider in _providers:
        _providers.remove(provider)


class NotDismissibleError(Exception):
    """O aviso não existe agora ou não aceita dispensa."""


async def _context(conn: asyncpg.Connection, periodo: date | None) -> AlertContext:
    today = today_brt()
    return AlertContext(
        today=today,
        periodo=periodo or today.replace(day=1),
        months=month_status(),
        owner_id=await get_owner_id(conn),
    )


async def _emitted(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    found: dict[str, Alert] = {}
    for provider in _providers:
        for alert in await provider(conn, ctx):
            found.setdefault(alert.key, alert)
    return list(found.values())


def _order(alerts: list[Alert]) -> list[Alert]:
    by_date = sorted(alerts, key=lambda a: (a.as_of or date.min, a.key), reverse=True)
    return sorted(by_date, key=lambda a: a.severity != "divergencia")


async def active_alerts(conn: asyncpg.Connection, periodo: date | None = None) -> AlertList:
    ctx = await _context(conn, periodo)
    emitted = await _emitted(conn, ctx)
    await conn.execute(queries.FORGET_GONE, [a.key for a in emitted])
    dismissed = {(r["key"], r["fingerprint"]) for r in await conn.fetch(queries.DISMISSED)}
    items = _order([a for a in emitted if (a.key, a.fingerprint) not in dismissed])
    return AlertList(
        items=items, total=len(items), data_until=await conn.fetchval(queries.DATA_UNTIL)
    )


async def dismiss(conn: asyncpg.Connection, key: str, fingerprint: str) -> None:
    ctx = await _context(conn, None)
    current = next((a for a in await _emitted(conn, ctx) if a.key == key), None)
    if current is None or not current.dismissible or current.fingerprint != fingerprint:
        raise NotDismissibleError(key)
    await conn.execute(queries.DISMISS, key, fingerprint)
