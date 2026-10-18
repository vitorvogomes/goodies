"""Aviso de vencimento das posições DeFi (Story 7.8 — FR-14, AD-10): provider de `wallet` na Central
de avisos, com o `Alert` de `common` (AD-1). Faltando 7 dias ou menos: "{Posição} vence em
{dd/mm/aaaa}." com a ação Ver posições manuais."""
from __future__ import annotations

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, fingerprint

MATURITY_WINDOW_DAYS = 7


async def defi_maturity_provider(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """"{Posição} vence em {dd/mm/aaaa}." — posição DeFi ativa a 7 dias ou menos do vencimento."""
    rows = await conn.fetch(
        "SELECT id, asset_symbol, maturity_date FROM defi_positions "
        "WHERE user_id = $1::uuid AND is_active AND maturity_date IS NOT NULL",
        ctx.owner_id,
    )
    alerts: list[Alert] = []
    for r in rows:
        days = (r["maturity_date"] - ctx.today).days
        if 0 <= days <= MATURITY_WINDOW_DAYS:
            alerts.append(
                Alert(
                    key=f"defi_vencendo:{r['id']}",
                    fingerprint=fingerprint(r["maturity_date"]),
                    severity="aviso",
                    message=f"{r['asset_symbol']} vence em {r['maturity_date']:%d/%m/%Y}.",
                    action=AlertAction(
                        label="Ver posições manuais", route="/ajustes/posicoes-manuais"
                    ),
                    as_of=ctx.today,
                )
            )
    return alerts
