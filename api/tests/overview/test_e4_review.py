"""Achados do code review do Épico 4 — cada teste trava um defeito corrigido."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from engines.common.dates import today_brt
from engines.common.owner import get_owner_id
from engines.portfolio import service as portfolio_service
from engines.wallet import service as wallet_service
from workers import job_alerts as ja
from workers import refresh

URL = "/api/v1/overview/painel"


@pytest.mark.asyncio
async def test_unpriced_open_position_leaves_both_sides(pool: Any) -> None:
    t = f"ZU{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        before = await portfolio_service.portfolio_snapshot(conn, owner)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) "
            "VALUES ($1, 'B3', $2, 'Ações Nacionais', 'compra', 100, 100, '2026-01-02')",
            owner,
            t,
        )
        try:
            after = await portfolio_service.portfolio_snapshot(conn, owner)
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", t)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{t}")
    assert after.contributed == before.contributed  # sem preço: sai do valor e do aportado
    assert after.stale is True


@pytest.mark.asyncio
async def test_oldest_scan_ignores_binance(pool: Any) -> None:
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO wallet_positions (user_id, chain, wallet_address, asset_symbol, quantity, "
            "source, scanned_at) VALUES ($1, 'binance', 'b', 'ZZB', 1, 'binance', now() - "
            "interval '30 days')",
            owner,
        )
        try:
            oldest = await wallet_service.oldest_scan(conn)
        finally:
            await conn.execute("DELETE FROM wallet_positions WHERE asset_symbol = 'ZZB'")
            await conn.execute(
                "DELETE FROM wallet_position_history h USING assets a "
                "WHERE a.id = h.asset_id AND a.key = 'crypto:ZZB'"
            )
            await conn.execute("DELETE FROM assets WHERE key = 'crypto:ZZB'")
    assert oldest is None or (datetime.now(UTC) - oldest).days < 30


def test_b3_lateness_follows_business_days() -> None:
    brt = ja.BRT
    friday = datetime(2026, 10, 16, 19, 0, tzinfo=brt)
    saturday_night = datetime(2026, 10, 17, 22, 0, tzinfo=brt)
    monday_night = datetime(2026, 10, 19, 21, 0, tzinfo=brt)
    assert refresh.b3_due(friday, saturday_night) is False
    assert refresh.b3_due(friday, monday_night) is True
    assert refresh.b3_due(None, monday_night) is True


def test_threshold_jobs_have_a_margin() -> None:
    spec = next(s for s in refresh.default_jobs() if s.name == "price_crypto")
    now = datetime.now(UTC)
    assert ja.is_late(spec, now - timedelta(seconds=spec.threshold_seconds + 60), now) is False
    assert ja.is_late(spec, now - timedelta(seconds=int(spec.threshold_seconds * 1.6)), now)


def test_fingerprint_ignores_new_attempts() -> None:
    success = datetime(2026, 10, 1, tzinfo=UTC)
    assert ja.alert_fingerprint(success) == ja.alert_fingerprint(success)


@pytest.mark.asyncio
async def test_price_worker_quotes_only_open_positions(pool: Any) -> None:
    from workers.price_workers import _symbols_in

    t = f"ZV{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES "
            "($1, 'B3', $2, 'Ações Nacionais', 'compra', 5, 10, '2026-01-02'), "
            "($1, 'B3', $2, 'Ações Nacionais', 'venda', 5, 12, '2026-02-02')",
            owner,
            t,
        )
        try:
            symbols = await _symbols_in(conn, ["Ações Nacionais"])
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", t)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{t}")
    assert t not in symbols


@pytest.mark.asyncio
async def test_variation_and_broker_cash_come_from_the_api(api, auth_headers, monkeypatch) -> None:
    from engines.portfolio import transit

    periodo = f"{today_brt():%Y-%m}"
    base = (await api.get(f"{URL}?periodo={periodo}", headers=auth_headers)).json()

    async def fake_transit(conn: Any, user_id: str) -> dict[str, Any]:
        return {"rails": [{"caixa_corretora_brl": 100.0}, {"caixa_corretora_brl": -30.0}]}

    monkeypatch.setattr(transit, "calculate_transit", fake_transit)
    with_cash = (await api.get(f"{URL}?periodo={periodo}", headers=auth_headers)).json()
    assert Decimal(str(with_cash["patrimonio"]["value"])) - Decimal(
        str(base["patrimonio"]["value"])
    ) == Decimal("100")
    assert "variacao_resultado_mes" in base
