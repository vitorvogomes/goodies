"""Ajustes › Preços manuais (Story 10.2 — FR-27, FR-35): só os ativos sem fonte de mercado — os de
`valuation = 'manual'` e os símbolos das carteiras e da DeFi sem cotação automática (ex.: a
Neobankless) —, com o preço e a data informados. A gravação é do `market` (POST
/api/v1/market/prices/{ticker}, `is_manual`, recusa quem tem fonte de mercado)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel

from engines.common.dates import today_brt
from engines.common.deps import AuthUser, Db
from engines.common.owner import get_owner_id
from engines.market import service as market_service
from engines.wallet import defi_anchors
from engines.wallet import service as wallet_service

router = APIRouter(prefix="/api/v1/portfolio/manual-prices", tags=["portfolio:manual-prices"])

_NOT_PRICED = {"caixinha:encerradas"}  # o bucket das encerradas não tem preço a informar


class ManualPrice(BaseModel):
    ticker: str
    label: str
    price_brl: Decimal | None  # None = ainda sem preço; texto decimal (unitário, até 8 casas)
    as_of: date | None
    is_manual: bool
    price_usd: Decimal | None = None  # o informado em dólar (token cripto)
    currency: str = "BRL"  # BRL | USD: a moeda em que o preço foi informado
    is_crypto: bool = False  # aceita o preço em US$


async def candidates(conn: asyncpg.Connection, owner: str) -> list[ManualPrice]:
    tickers: dict[str, str] = {
        r["price_ref"]: r["name"]
        for r in await conn.fetch(
            "SELECT price_ref, name FROM assets WHERE valuation = 'manual' AND is_active "
            "AND key <> ALL($1::text[])",
            list(_NOT_PRICED),
        )
    }
    crypto_assets = {
        r["price_ref"]
        for r in await conn.fetch("SELECT price_ref FROM assets WHERE class = 'cripto'")
    }
    held = {w["asset_symbol"] for w in await wallet_service.list_wallet_positions(conn, owner)}
    held |= {d["asset_symbol"] for d in await wallet_service.list_defi_valued(conn, owner)}
    for symbol in sorted(held - set(tickers)):
        if not await market_service.has_market_source(conn, symbol):
            tickers[symbol] = symbol
    # v2.2: token DeFi com saldo em US$ informado — o saldo é a fonte, não o preço manual
    for symbol in await defi_anchors.anchored_symbols(conn):
        tickers.pop(symbol, None)
    rows = {
        r["ticker"]: r
        for r in await conn.fetch(
            "SELECT ticker, price_brl, price_usd, source, fetched_at, is_manual FROM asset_prices "
            "WHERE ticker = ANY($1::text[])",
            list(tickers),
        )
    }
    out = []
    for ticker, label in sorted(tickers.items(), key=lambda i: i[1].lower()):
        row = rows.get(ticker)
        out.append(
            ManualPrice(
                ticker=ticker,
                label=label,
                price_brl=row["price_brl"] if row else None,
                as_of=today_brt(row["fetched_at"]) if row else None,
                is_manual=bool(row["is_manual"]) if row else False,
                price_usd=row["price_usd"] if row else None,
                currency="USD" if row and row["source"] == market_service.MANUAL_USD else "BRL",
                is_crypto=ticker in held or ticker in crypto_assets,
            )
        )
    return out


@router.get("", response_model=list[ManualPrice])
async def list_manual_prices(user: AuthUser, db: Db) -> list[ManualPrice]:
    return await candidates(db, await get_owner_id(db))
