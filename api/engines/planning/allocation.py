"""Alocação × meta (Story 8.3 — FR-14, FR-21, AD-11): o cálculo é de `planning`, sobre as
posições do `portfolio`. A base exclui os ativos de objetivos (bloco "Objetivos", ainda no
patrimônio); o bloco cripto entra pelo valor atual por ativo. Classe fora da banda (|atual − meta|
> banda) vira aviso.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, fingerprint
from engines.portfolio import positions as positions_service
from engines.portfolio.positions import GOALS_BLOCK, PositionClass

from . import calc, goals, targets

_CENT = Decimal("0.01")


def _q(value: Decimal | None) -> Decimal | None:
    return value.quantize(_CENT) if value is not None else None


async def apply_allocation(
    conn: asyncpg.Connection, classes: list[PositionClass], month: date
) -> None:
    """Preenche alocação, meta, banda e desvio das classes (e dos ativos dentro da classe) com as
    metas vigentes no mês."""
    class_rows = await targets.class_targets(conn, month=month)
    asset_rows = await targets.asset_targets(conn, month=month)
    base = [c for c in classes if c.key != GOALS_BLOCK]
    shares = calc.allocation_shares(
        {c.key: c.valor for c in base},
        {k: Decimal(r["target_pct"]) for k, r in class_rows.items()},
    )
    for c in base:
        share = shares[c.key]
        row = class_rows.get(c.key)
        c.alocacao, c.meta, c.desvio_pp = _q(share.atual), _q(share.meta), _q(share.desvio)
        c.banda = _q(Decimal(row["band_pp"])) if row else None
        c.fora_banda = calc.out_of_band(share.desvio, c.banda)
        own = asset_rows.get(c.key, {})
        asset_shares = calc.allocation_shares(
            {a.asset_id or a.symbol: a.valor.value or Decimal(0) for a in c.assets}, own
        )
        for a in c.assets:
            s = asset_shares[a.asset_id or a.symbol]
            a.alocacao, a.meta, a.desvio_pp = _q(s.atual), _q(s.meta), _q(s.desvio)


async def current_classes(conn: asyncpg.Connection, owner: str, month: date) -> list[PositionClass]:
    """As posições do fim do mês com o bloco de objetivos à parte e a alocação preenchida."""
    linked = frozenset(await goals.linked_assets(conn))
    classes = await positions_service.positions_period(conn, owner, None, month, set_aside=linked)
    await apply_allocation(conn, classes, month)
    return classes


def _num(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


async def allocation_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """ "{Classe} em {x,xx}%, meta {y,yy}% ± {b} p.p." (Ver aportes) para a classe fora da banda."""
    month = ctx.today.replace(day=1)
    labels = dict(targets.CLASS_LABELS)
    out: list[Alert] = []
    for c in await current_classes(conn, ctx.owner_id, month):
        if not c.fora_banda or c.alocacao is None or c.meta is None or c.banda is None:
            continue
        band = targets.pct_text(c.banda)
        out.append(
            Alert(
                key=f"fora_da_banda:{c.key}",
                fingerprint=fingerprint(c.key, c.meta, c.banda, month),
                severity="aviso",
                message=f"{labels.get(c.key, c.label)} em {_num(c.alocacao)}%, "
                f"meta {_num(c.meta)}% ± {band} p.p.",
                action=AlertAction(label="Ver aportes", route="/investimentos/aportes"),
                as_of=ctx.today,
            )
        )
    return out
