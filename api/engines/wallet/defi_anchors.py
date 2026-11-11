"""DeFi pelo saldo em US$ (v2.2): o saldo que o protocolo mostra numa data, com a quantidade de
tokens dessa data e, se informado, o APY (% a.a.). O preço por token (saldo ÷ quantidade) rende o
APY por dia até o próximo saldo (sem APY, parado) e vai para o chokepoint de preços como manual em
dólar (`defi_anchor`): o R$ segue a cotação, o histórico guarda o dia, e Posições/sleeve/XIRR leem
como sempre. Só para token sem cotação de mercado. Repreço diário junto com o `manual_usd`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from config import settings
from engines.common.dates import today_brt
from engines.market import service as market_service

DEFI_ANCHOR = "defi_anchor"  # `source` do preço derivado do saldo informado
_CENT = Decimal("0.01")


class FutureAnchorError(ValueError):
    pass


class MarketPricedError(ValueError):
    """O token tem cotação de mercado: o valor segue o preço, o saldo seria só a quantidade."""


@dataclass(frozen=True)
class Anchor:
    ref_date: date
    value_usd: Decimal
    apy: Decimal | None  # % a.a.
    quantity: Decimal = Decimal(1)  # tokens da posição na data do saldo


def price_on(anchors: list[Anchor], day: date) -> Decimal | None:
    """O preço por token em US$ no dia: saldo ÷ quantidade do saldo mais recente até `day`, com o
    APY composto por dia. É o preço (não o valor) que segue: um depósito depois do saldo entra
    por ele, em vez de diluir o saldo informado."""
    past = [a for a in anchors if a.ref_date <= day]
    if not past:
        return None
    a = max(past, key=lambda x: x.ref_date)
    growth = (
        (1 + a.apy / 100) ** (Decimal((day - a.ref_date).days) / Decimal(365))
        if a.apy
        else Decimal(1)
    )
    return (a.value_usd / a.quantity * growth).quantize(Decimal("0.00000001"))


class AnchorIn(BaseModel):
    as_of: date
    value_usd: Decimal = Field(ge=0)
    apy: Decimal | None = Field(default=None, gt=-100, le=1000)


class AnchorOut(BaseModel):
    as_of: date
    value_usd: float
    apy: float | None


async def anchors_by_position(conn: Any) -> dict[str, list[Anchor]]:
    out: dict[str, list[Anchor]] = defaultdict(list)
    if not await conn.fetchval("SELECT to_regclass('defi_balance_anchors') IS NOT NULL"):
        return out  # base antiga (dados_reais migra passo a passo)
    for r in await conn.fetch(
        "SELECT defi_position_id::text AS pid, ref_date, value_usd, apy, quantity "
        "FROM defi_balance_anchors ORDER BY ref_date"
    ):
        out[r["pid"]].append(
            Anchor(
                r["ref_date"],
                Decimal(r["value_usd"]),
                Decimal(r["apy"]) if r["apy"] else None,
                Decimal(r["quantity"]),
            )
        )
    return out


def latest(anchors: list[Anchor]) -> AnchorOut | None:
    if not anchors:
        return None
    a = max(anchors, key=lambda x: x.ref_date)
    return AnchorOut(
        as_of=a.ref_date, value_usd=float(a.value_usd), apy=float(a.apy) if a.apy else None
    )


async def anchored_symbols(conn: Any) -> set[str]:
    """Tokens com saldo informado numa posição ativa: o saldo é a fonte (não o preço manual)."""
    if not await conn.fetchval("SELECT to_regclass('defi_balance_anchors') IS NOT NULL"):
        return set()
    rows = await conn.fetch(
        "SELECT DISTINCT p.asset_symbol FROM defi_balance_anchors b "
        "JOIN defi_positions p ON p.id = b.defi_position_id WHERE p.is_active"
    )
    return {r["asset_symbol"] for r in rows}


async def market_priced(conn: asyncpg.Connection, symbol: str) -> bool:
    """Token com cotação automática (CoinGecko, ou preço automático já gravado): o saldo em US$
    não vale para ele — gravaria um preço manual e congelaria a cotação de quem tem o token."""
    if settings.coingecko_ids.get(symbol.upper()):
        return True
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM asset_prices WHERE ticker = $1 AND NOT is_manual)",
            symbol,
        )
    )


async def save_anchor(
    conn: asyncpg.Connection, position_id: str, user_id: str, body: AnchorIn
) -> bool:
    """Grava o saldo do dia com a quantidade de hoje da posição (substitui o do mesmo dia) e refaz
    o preço do token. False = sem a posição."""
    if body.as_of > today_brt():
        raise FutureAnchorError("A data não pode ser depois de hoje.")
    async with conn.transaction():
        pos = await conn.fetchrow(
            "SELECT asset_symbol, balance FROM defi_positions "
            "WHERE id = $1::uuid AND user_id = $2::uuid",
            position_id,
            user_id,
        )
        if pos is None:
            return False
        if await market_priced(conn, pos["asset_symbol"]):
            raise MarketPricedError(
                f"{pos['asset_symbol']} tem cotação de mercado: atualize só a quantidade."
            )
        if Decimal(pos["balance"]) <= 0:
            raise MarketPricedError("Informe a quantidade da posição antes do saldo.")
        await conn.execute(
            "INSERT INTO defi_balance_anchors (defi_position_id, ref_date, value_usd, apy, "
            "quantity) VALUES ($1::uuid, $2, $3, $4, $5) ON CONFLICT (defi_position_id, ref_date) "
            "DO UPDATE SET value_usd = EXCLUDED.value_usd, apy = EXCLUDED.apy, "
            "quantity = EXCLUDED.quantity",
            position_id,
            body.as_of,
            body.value_usd.quantize(_CENT),
            body.apy,
            Decimal(pos["balance"]),
        )
    await reprice(conn)
    return True


async def reprice(conn: asyncpg.Connection, day: date | None = None) -> int:
    """Preço de hoje de cada token com saldo informado numa posição ativa: a média dos preços por
    token das posições dele, pesada pela quantidade (US$; o R$ pela cotação). Token que perdeu o
    saldo (posição apagada, inativa ou com outro símbolo) volta a preço manual em dólar, com o
    último preço: segue a cotação e reaparece em Preços manuais. Quantos foram gravados."""
    day = day or today_brt()
    anchors = await anchors_by_position(conn)
    rows = (
        await conn.fetch(
            "SELECT id::text AS pid, asset_symbol, balance FROM defi_positions "
            "WHERE is_active AND id = ANY($1::uuid[])",
            list(anchors),
        )
        if anchors
        else []
    )
    weighted: dict[str, Decimal] = defaultdict(Decimal)
    qty: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        price = price_on(anchors[r["pid"]], day)
        if price is None:
            continue
        q = Decimal(r["balance"])
        weighted[r["asset_symbol"]] += price * q
        qty[r["asset_symbol"]] += q
    # o token que saiu do saldo informado não fica preso num preço que ninguém atualiza
    await conn.execute(
        "UPDATE asset_prices SET source = $1 WHERE source = $2 AND NOT (ticker = ANY($3::text[]))",
        market_service.MANUAL_USD,
        DEFI_ANCHOR,
        list(qty),
    )
    done = 0
    for sym, q in qty.items():
        if q <= 0:
            continue
        price_usd = (weighted[sym] / q).quantize(Decimal("0.00000001"))
        if await market_service.set_manual_usd(conn, sym, price_usd, source=DEFI_ANCHOR) is None:
            return done  # sem cotação do dólar: tenta no próximo ciclo
        done += 1
    return done
