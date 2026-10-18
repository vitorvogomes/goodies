"""Saldo informado da renda fixa pelo CDI (pendência P28): o saldo que o app do banco mostra numa
data — ou cotas × valor da cota, no fundo da Reserva — e o %CDI do ativo, editáveis em Ajustes ›
Preços manuais. O saldo mais recente até a data substitui as operações até ele na valoração
(`rf.cdi_value`); salvar regrava o preço de hoje pelo chokepoint (fonte `cdi`, não manual).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field, model_validator

from engines.common.cache import invalidate_xirr_cache
from engines.common.dates import today_brt
from engines.common.money import Money
from engines.common.owner import get_owner_id
from engines.market import service as market_service
from engines.portfolio import calc
from engines.portfolio.rf import cdi_value

_CENT = Decimal("0.01")


class FutureAnchorError(ValueError):
    pass


class AnchorIn(BaseModel):
    as_of: date
    value: Decimal | None = Field(default=None, ge=0)
    quotas: Decimal | None = Field(default=None, gt=0)
    quota_value: Decimal | None = Field(default=None, gt=0)
    pct_cdi: Decimal | None = Field(default=None, gt=0, le=1000)

    @model_validator(mode="after")
    def _value_or_quotas(self) -> AnchorIn:
        by_quotas = self.quotas is not None and self.quota_value is not None
        if (self.quotas is None) != (self.quota_value is None):
            raise ValueError("Informe as cotas e o valor da cota.")
        if not by_quotas and self.value is None:
            raise ValueError("Informe o saldo ou as cotas e o valor da cota.")
        return self

    def amount(self) -> Decimal:
        if self.quotas is not None and self.quota_value is not None:
            return (self.quotas * self.quota_value).quantize(_CENT)
        assert self.value is not None
        return self.value.quantize(_CENT)


class RfRow(BaseModel):
    ticker: str
    label: str
    pct_cdi: Decimal | None
    anchor_date: date | None = None
    value: Money | None = None
    quotas: Decimal | None = None
    quota_value: Decimal | None = None


_LIST = (
    "SELECT a.id, a.price_ref, a.name, a.pct_cdi, b.ref_date, b.value, b.quotas, b.quota_value "
    "FROM assets a LEFT JOIN LATERAL (SELECT * FROM rf_balance_anchors x WHERE x.asset_id = a.id "
    "ORDER BY x.ref_date DESC LIMIT 1) b ON true "
    "WHERE a.valuation = 'cdi' AND a.is_active {where} ORDER BY a.name"
)


def _row(r: Any) -> RfRow:
    return RfRow(
        ticker=r["price_ref"],
        label=r["name"],
        pct_cdi=r["pct_cdi"],
        anchor_date=r["ref_date"],
        value=r["value"],
        quotas=r["quotas"],
        quota_value=r["quota_value"],
    )


async def list_rf(conn: asyncpg.Connection) -> list[RfRow]:
    """Ativos valorados pelo CDI com o saldo informado mais recente (quando houver)."""
    return [_row(r) for r in await conn.fetch(_LIST.format(where=""))]


async def anchor_map(conn: Any) -> dict[str, list[tuple[date, Decimal]]]:
    """Símbolo (`price_ref`) → saldos informados (data, valor), para `rf.cdi_value`."""
    out: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    if not await conn.fetchval("SELECT to_regclass('rf_balance_anchors') IS NOT NULL"):
        return out  # base antiga (dados_reais migra passo a passo)
    for r in await conn.fetch(
        "SELECT a.price_ref, b.ref_date, b.value FROM rf_balance_anchors b "
        "JOIN assets a ON a.id = b.asset_id ORDER BY b.ref_date"
    ):
        out[r["price_ref"]].append((r["ref_date"], Decimal(r["value"])))
    return out


async def save_anchor(conn: asyncpg.Connection, ticker: str, body: AnchorIn) -> RfRow:
    if body.as_of > today_brt():
        raise FutureAnchorError("A data não pode ser depois de hoje.")
    asset = await conn.fetchrow(
        "SELECT id, pct_cdi FROM assets WHERE price_ref = $1 AND valuation = 'cdi'", ticker
    )
    if asset is None:
        raise LookupError(ticker)
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO rf_balance_anchors (asset_id, ref_date, value, quotas, quota_value) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (asset_id, ref_date) DO UPDATE SET "
            "value = EXCLUDED.value, quotas = EXCLUDED.quotas, quota_value = EXCLUDED.quota_value",
            asset["id"],
            body.as_of,
            body.amount(),
            body.quotas,
            body.quota_value,
        )
        if body.pct_cdi is not None:
            await conn.execute(
                "UPDATE assets SET pct_cdi = $2 WHERE id = $1", asset["id"], body.pct_cdi
            )
    await _reprice(conn, ticker, body.pct_cdi or Decimal(asset["pct_cdi"] or 100))
    await invalidate_xirr_cache(await get_owner_id(conn))
    row = await conn.fetchrow(_LIST.format(where="AND a.id = $1"), asset["id"])
    return _row(row)


async def _reprice(conn: asyncpg.Connection, ticker: str, pct: Decimal) -> None:
    """O preço de hoje (valor ÷ quantidade), como o job `rf_cdi` grava."""
    owner = await get_owner_id(conn)
    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade, valor_unitario, data_operacao "
        "FROM asset_operations WHERE user_id = $1 AND asset_symbol = $2 ORDER BY data_operacao",
        owner,
        ticker,
    )
    qty = calc.quantity(ops)
    if not ops or qty <= 0:
        return
    today = today_brt()
    series = await market_service.cdi_daily(conn, ops[0]["data_operacao"], today)
    value = cdi_value(ops, today, pct, series, anchors=(await anchor_map(conn))[ticker])
    await market_service.upsert_price(
        conn, ticker, float(value.value / qty), source="cdi", is_manual=False
    )
