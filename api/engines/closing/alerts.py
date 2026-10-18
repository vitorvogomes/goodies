"""Avisos do fechamento (AD-10 — Story 5.6): ajuste em mês fechado e mês que segue aberto.

O ajuste compara o congelado com os totais de fluxo de `ledger/calc` ao vivo e mostra a métrica com
a maior diferença; o cálculo fica em cache por mês e versão, refeito só quando `dirty_count` muda.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, brl, fingerprint
from engines.common.cache import cache
from engines.common.dates import MIN_MONTH, month_label
from engines.ledger import service as ledger_service

# Métrica de fluxo do snapshot → atributo de `LedgerMonth` e nome na mensagem.
_FLOWS = (
    ("gastos", "gastos", "gastos"),
    ("receitas", "receitas", "receitas"),
    ("trabalho", "trabalho", "receita do trabalho"),
    ("resgates", "resgates", "resgates"),
    ("devolucoes", "devolucoes", "devoluções"),
    ("investido", "investido", "investido no mês"),
    ("resultado_mes", "resultado", "resultado do mês"),
)
_CENT = Decimal("0.01")
_TTL = 30 * 86400


def _next(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


async def _diffs(conn: asyncpg.Connection, close: asyncpg.Record) -> list[list[str]]:
    """[métrica, congelado, ao vivo] das métricas de fluxo que mudam, a maior diferença primeiro."""
    month, version, count = close["month"], close["version"], close["dirty_count"]
    key = f"closing:ajuste:{month:%Y-%m}"
    stamp = close["closed_at"].isoformat()  # distingue a versão entre bancos (teste × real)
    hit = await cache().get(key)
    if hit and (hit.get("version"), hit.get("count"), hit.get("stamp")) == (version, count, stamp):
        cached = hit.get("rows")
        if isinstance(cached, list):
            return [[str(x) for x in row] for row in cached]
    frozen = await conn.fetchrow(
        "SELECT * FROM month_summary_totals WHERE month = $1 AND version = $2", month, version
    )
    live = await ledger_service.ledger_month(conn, month)
    found: list[tuple[Decimal, int, list[str]]] = []
    for i, (column, attr, name) in enumerate(_FLOWS):
        before = frozen[column]
        after = Decimal(getattr(live, attr)).quantize(_CENT)
        if before is None or before.quantize(_CENT) == after:
            continue
        found.append((abs(after - before), i, [name, str(before), str(after)]))
    rows = [r for *_, r in sorted(found, key=lambda f: (-f[0], f[1]))]
    await cache().set(key, {"version": version, "count": count, "stamp": stamp, "rows": rows}, _TTL)
    return rows


async def adjustment_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider: "Ajuste em {mês}, já fechado. …" para cada mês fechado e `dirty`."""
    closes = await conn.fetch(
        "SELECT DISTINCT ON (month) month, version, status, closed_at, dirty, dirty_count "
        "FROM month_closes "
        "ORDER BY month, version DESC"
    )
    out: list[Alert] = []
    for close in closes:
        if close["status"] != "closed" or not close["dirty"]:
            continue
        month = close["month"]
        message = f"Ajuste em {month_label(month)}, já fechado. O resumo congelado não mudou."
        rows = await _diffs(conn, close)
        if rows:
            name, before, after = rows[0]
            message += (
                f" Se reabrir, {name} passa de {brl(Decimal(before))} para {brl(Decimal(after))}"
            )
            message += f", e mais {len(rows) - 1}." if len(rows) > 1 else "."
        out.append(
            Alert(
                key=f"ajuste:{month:%Y-%m}",
                fingerprint=fingerprint(close["version"], close["dirty_count"]),
                severity="aviso",
                message=message,
                action=AlertAction(
                    label="Reabrir mês",
                    route="/visao-geral/historico",
                    params={"reabrir": f"{month:%Y-%m}"},
                ),
                as_of=ctx.today,
            )
        )
    return out


async def open_month_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider: mês aberto depois do dia 15 do mês seguinte (o consolidado B3 e o OFX do MEI já
    deveriam ter chegado) — "{Mês} segue aberto. Confira o saldo e feche.". Conta a partir do mês
    seguinte ao último fechado (o atraso anterior é a trilha do Assistente de recuperação)."""
    last_closed = await conn.fetchval("SELECT max(month) FROM month_closes WHERE status = 'closed'")
    month = _next(last_closed) if last_closed is not None else MIN_MONTH
    cutoff = ctx.today.replace(day=1)
    if ctx.today.day <= 15:
        cutoff = date(cutoff.year - (cutoff.month == 1), (cutoff.month - 2) % 12 + 1, 1)
    out: list[Alert] = []
    while _next(month) <= cutoff:
        if not await ctx.months.is_closed(conn, month):
            name = month_label(month)
            out.append(
                Alert(
                    key=f"mes_aberto:{month:%Y-%m}",
                    fingerprint=fingerprint(month),
                    severity="aviso",
                    message=f"{name[0].upper()}{name[1:]} segue aberto. Confira o saldo e feche.",
                    action=AlertAction(
                        label="Ir para Histórico",
                        route="/visao-geral/historico",
                        params={"periodo": f"{month:%Y-%m}"},
                    ),
                    as_of=ctx.today,
                )
            )
        month = _next(month)
    return out
