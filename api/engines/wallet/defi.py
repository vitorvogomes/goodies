"""Lógica pura de alertas DeFi (STORY-04-09), sem I/O.

Compute-on-read (mesmo padrão de `engines/ledger/service.py`): `today` injetado →
determinístico e testável sem relógio/DB. Reusa o `Alert` do Ledger. A persistência
(active_alerts) e o Alert Engine consolidado ficam para o m5.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from engines.ledger.service import Alert


@dataclass
class DefiMaturity:
    asset_symbol: str
    maturity_date: datetime.date | None
    protocol: str | None = None


def defi_maturity_alerts(
    positions: list[DefiMaturity],
    today: datetime.date,
    windows: tuple[int, ...] = (30, 7),
) -> list[Alert]:
    """Posições DeFi vencendo dentro das janelas (default 30d=warning, ≤7d=critical).

    Uma janela mais apertada (≤7) vence: dispara um alerta por posição, com a severidade
    da menor janela em que ela já entrou. Posição sem `maturity_date` ou já vencida é ignorada.
    """
    alerts: list[Alert] = []
    for pos in positions:
        if pos.maturity_date is None:
            continue
        days = (pos.maturity_date - today).days
        if days < 0:
            continue  # já vencida
        matched = [w for w in sorted(windows) if days <= w]
        if not matched:
            continue  # fora de todas as janelas
        tightest = matched[0]
        alerts.append(
            Alert(
                type="defi_maturity",
                severity="critical" if tightest <= 7 else "warning",
                title="Posição DeFi vencendo",
                message=f"{pos.asset_symbol} vence em {days} dia(s) ({pos.maturity_date})",
                data={
                    "asset_symbol": pos.asset_symbol,
                    "maturity_date": str(pos.maturity_date),
                    "days_until": days,
                    "protocol": pos.protocol or "",
                },
            )
        )
    return alerts
