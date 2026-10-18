"""Aviso de worker com falha ou atrasado (Story 4.3 — FR-14, AD-10): substitui o Discord até a v2.1.

Um job sem sucesso dentro do seu intervalo (`JobSpec.threshold_seconds`, ou o vencimento próprio)
vira "{Job} sem atualização desde {dd/mm/aaaa hh:mm}."; o backup que falhou vira "Backup do banco
falhou em {dd/mm/aaaa}.". Com o notebook desligado por dias, o catch-up roda ao abrir o app: o aviso
só aparece se o catch-up tentou e falhou, ou depois de 30 min de máquina ligada sem sucesso. Some
quando o job volta a dar certo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, fingerprint
from workers import refresh

BRT = ZoneInfo("America/Sao_Paulo")
GRACE = timedelta(minutes=30)
LABELS = {
    "price_b3": "Preço B3",
    "price_crypto": "Preço cripto",
    "wallet_scan": "Scan de carteiras",
    "benchmark": "CDI/IPCA",
    "db_backup": "Backup do banco",
    "restore_check": "Conferência do backup",
}
_ACTION = AlertAction(label="Ver atualização", route="/refresh")
# O run grava o horário em que começou e o limiar é o próprio intervalo do cron: sem folga, todo
# ciclo agendado "atrasaria" enquanto roda. Atraso = mais de 1,5 intervalo sem sucesso.
LATE_FACTOR = 1.5
DUE_MARGIN = timedelta(hours=1)


def is_late(spec: refresh.JobSpec, success: datetime | None, now: datetime) -> bool:
    if spec.is_due is not None:  # vencimento próprio (dia útil, mensal): com 1 h de folga
        return spec.is_due(success, now - DUE_MARGIN)
    if success is None:
        return True
    return (now - success).total_seconds() >= spec.threshold_seconds * LATE_FACTOR


def alert_fingerprint(success: datetime | None) -> str:
    """Só o último sucesso: uma nova tentativa que falha não faz o aviso dispensado voltar."""
    return fingerprint(success)


async def job_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    now = datetime.now(UTC)
    started = refresh.PROCESS_STARTED
    rows = {
        r["job"]: r
        for r in await conn.fetch("SELECT job, last_run, ok, last_success_at FROM job_runs")
    }
    alerts: list[Alert] = []
    for spec in refresh.default_jobs():
        r = rows.get(spec.name)
        success = r["last_success_at"] if r is not None else None
        if not is_late(spec, success, now):
            continue
        tried_and_failed = r is not None and r["ok"] is False and r["last_run"] >= started
        if not tried_and_failed and now - started < GRACE:
            continue  # o catch-up ainda pode resolver
        if spec.name == "db_backup" and r is not None and r["ok"] is False:
            message = f"Backup do banco falhou em {r['last_run'].astimezone(BRT):%d/%m/%Y}."
        elif success is not None:
            message = (
                f"{LABELS.get(spec.name, spec.name)} sem atualização desde "
                f"{success.astimezone(BRT):%d/%m/%Y %H:%M}."
            )
        else:
            message = f"{LABELS.get(spec.name, spec.name)} nunca foi atualizado."
        alerts.append(
            Alert(
                key=f"job:{spec.name}",
                fingerprint=alert_fingerprint(success),
                severity="aviso",
                message=message,
                action=_ACTION,
                as_of=(success or now).astimezone(BRT).date(),
            )
        )
    return alerts
