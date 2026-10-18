"""Story 5.1 — histórico de preço e de carteira: o dia de cada coleta fica guardado (o último preço
do dia vence), a leitura até uma data nunca devolve o preço de hoje, e posição que sai da carteira
vira quantidade 0 naquele dia."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.market import service as market
from engines.wallet import service as wallet


@pytest.mark.asyncio
async def test_price_history_and_read_until_a_date(pool: Any) -> None:
    t = f"ZH{uuid.uuid4().hex[:4].upper()}"
    async with pool.acquire() as conn:
        try:
            await market.upsert_price(conn, t, 10.0, source="brapi", is_manual=False)
            await market.upsert_price(conn, t, 11.0, source="brapi", is_manual=False)
            rows = await conn.fetch(
                "SELECT ref_date, price_brl FROM asset_price_history WHERE ticker = $1", t
            )
            assert [(r["ref_date"], r["price_brl"]) for r in rows] == [
                (today_brt(), Decimal("11.00000000"))
            ]
            await conn.execute(
                "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, is_manual) "
                "VALUES ($1, $2, 9, 'brapi', false)",
                t,
                date(2026, 3, 31),
            )
            march = await market.price_as_of(conn, t, date(2026, 4, 15))
            assert (march.value, march.as_of) == (Decimal("9"), date(2026, 3, 31))
            before = await market.price_as_of(conn, t, date(2026, 1, 31))
            assert before.value is None and before.unavailable_reason == "sem_preco"
        finally:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", t)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", t)


@pytest.mark.asyncio
async def test_wallet_history_one_row_per_day_and_zero_when_removed(pool: Any) -> None:
    sym = f"ZW{uuid.uuid4().hex[:4].upper()}"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        try:
            await wallet.upsert_manual_wallet_position(conn, owner, "liquid", sym, 2.0)
            await wallet.upsert_manual_wallet_position(conn, owner, "liquid", sym, 3.0)
            await wallet.delete_manual_wallet_position(conn, owner, "liquid", sym)
            rows = await conn.fetch(
                "SELECT h.ref_date, h.quantity FROM wallet_position_history h "
                "JOIN assets a ON a.id = h.asset_id WHERE a.key = $1",
                f"crypto:{sym}",
            )
            assert [(r["ref_date"], r["quantity"]) for r in rows] == [(today_brt(), 0)]
            held = await wallet.positions_as_of(conn, today_brt() - timedelta(days=1))
            assert all(p["asset_symbol"] != sym for p in held)
        finally:
            await conn.execute(
                "DELETE FROM wallet_position_history h USING assets a "
                "WHERE a.id = h.asset_id AND a.key = $1",
                f"crypto:{sym}",
            )
            await conn.execute("DELETE FROM assets WHERE key = $1", f"crypto:{sym}")


def test_month_end_scan_is_due_on_the_last_day() -> None:
    from datetime import UTC, datetime

    from workers.refresh import month_end_scan_due

    last_day = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)
    assert month_end_scan_due(datetime(2026, 10, 30, 23, 0, tzinfo=UTC), last_day) is True
    assert month_end_scan_due(datetime(2026, 10, 31, 13, 0, tzinfo=UTC), last_day) is False
    mid = datetime(2026, 10, 15, 15, 0, tzinfo=UTC)
    assert month_end_scan_due(datetime(2026, 10, 15, 13, 0, tzinfo=UTC), mid) is False
