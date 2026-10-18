"""Story 7.9 — conciliação com o consolidado B3 e com as carteiras (AD-13): quantidade exata nas
ações/FII/ETF, 0,01 título no Tesouro, cripto sem divergência, RF "valor calculado"; scan com mais
de 14 h desde a última tentativa = desatualizado; rota com B3 + carteiras + "tudo bate"."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from engines.common.owner import get_owner_id
from engines.portfolio import calc
from engines.portfolio import reconciliation as recon
from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers

REF = date(2097, 12, 31)


async def _op(conn: Any, owner: str, symbol: str, category: str, qty: str) -> Any:
    return await conn.fetchval(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
        "quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3-movimentacao', $2, $3, "
        "'compra', $4, 10, '2097-06-10') RETURNING asset_id",
        owner,
        symbol,
        category,
        Decimal(qty),
    )


@pytest.mark.asyncio
async def test_b3_quantities_and_tolerances(pool: Any) -> None:
    tag = uuid.uuid4().hex[:3].upper()
    ok, off, td = f"ZK{tag}3", f"ZL{tag}3", f"TD-{tag}"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        assets = {
            ok: await _op(conn, owner, ok, "Ações Nacionais", "10"),
            off: await _op(conn, owner, off, "FIIs", "7"),
            td: await _op(conn, owner, td, "Aposentadoria", "1.23"),
        }
        for symbol, qty in ((ok, "10"), (off, "6"), (td, "1.24")):
            await conn.execute(
                "INSERT INTO broker_position_snapshots (ref_date, asset_id, quantity, "
                "reported_value) VALUES ($1, $2, $3, 1)",
                REF,
                assets[symbol],
                Decimal(qty),
            )
        try:
            b3 = await recon.b3_reconciliation(conn, owner, REF)
            checks = await recon.close_checks(conn, date(2097, 12, 1))
        finally:
            await conn.execute("DELETE FROM broker_position_snapshots WHERE ref_date = $1", REF)
            await conn.execute(
                "DELETE FROM asset_operations WHERE asset_symbol = ANY($1::text[])", list(assets)
            )
            await conn.execute(
                "DELETE FROM assets WHERE id = ANY($1::uuid[])", list(assets.values())
            )
    rows = {r.symbol: r for r in b3.rows}
    assert rows[ok].status == "conferido"
    assert (rows[off].status, rows[off].diff) == ("divergente", Decimal(1))
    assert rows[td].status == "conferido"  # 0,01 título
    app, origin = recon._qty(rows[off].app), recon._qty(rows[off].origin)
    assert (app, origin) == ("7", "6")  # "{ativo}: 7 no app, 6 no consolidado B3."
    assert [c["code"] for c in checks] == ["posicao_divergente"]
    assert checks[0]["kind"] == "confirma" and off in checks[0]["message"]


@pytest.mark.asyncio
async def test_close_check_without_snapshot_is_silent(pool: Any) -> None:
    async with pool.acquire() as conn:
        assert await recon.close_checks(conn, date(2096, 3, 1)) == []


@pytest.mark.asyncio
async def test_scan_staleness_counts_from_last_attempt(pool: Any) -> None:
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        saved = await conn.fetchrow("SELECT * FROM job_runs WHERE job = 'wallet_scan'")
        attempt = datetime(2097, 1, 1, 8, tzinfo=UTC)
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('wallet_scan', $1, false) "
            "ON CONFLICT (job) DO UPDATE SET last_run = EXCLUDED.last_run",
            attempt,
        )
        try:
            fresh = await recon.wallet_reconciliation(
                conn, owner, now=attempt + timedelta(hours=13)
            )
            late = await recon.wallet_reconciliation(conn, owner, now=attempt + timedelta(hours=15))
        finally:
            if saved is None:
                await conn.execute("DELETE FROM job_runs WHERE job = 'wallet_scan'")
            else:
                await conn.execute(
                    "UPDATE job_runs SET last_run = $1 WHERE job = 'wallet_scan'", saved["last_run"]
                )
    assert (fresh.stale, late.stale) == (False, True)
    assert late.attempt_at == attempt


def test_qty_text() -> None:
    assert recon._qty(Decimal("1.2300")) == "1,23"
    assert recon._qty(Decimal("10")) == "10"
    assert recon._qty(None) == "—"


@pytest.mark.asyncio
async def test_reconciliation_route(api, auth_headers) -> None:
    r = await api.get("/api/v1/portfolio/reconciliation", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"b3", "wallets", "all_ok"}
    assert {"ref_date", "rows"} <= set(body["b3"])
    v1 = await api.get("/api/v1/wallets/reconciliation", headers=auth_headers)
    assert v1.status_code == 200  # o caminho da tela v1 segue


@pytest.mark.asyncio
async def test_stale_scan_alert_uses_catalog_text(pool: Any) -> None:
    from engines.common.alerts import AlertContext

    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        saved = await conn.fetchrow("SELECT * FROM job_runs WHERE job = 'wallet_scan'")
        await conn.execute(
            "INSERT INTO job_runs (job, last_run, ok) VALUES ('wallet_scan', $1, false) "
            "ON CONFLICT (job) DO UPDATE SET last_run = EXCLUDED.last_run",
            datetime(2001, 1, 1, 8, tzinfo=UTC),
        )
        try:
            ctx = AlertContext(
                today=date(2001, 1, 2), periodo=date(2001, 1, 1), months=None, owner_id=owner
            )  # type: ignore[arg-type]
            alerts = await recon.reconciliation_alerts(conn, ctx)
        finally:
            if saved is None:
                await conn.execute("DELETE FROM job_runs WHERE job = 'wallet_scan'")
            else:
                await conn.execute(
                    "UPDATE job_runs SET last_run = $1 WHERE job = 'wallet_scan'", saved["last_run"]
                )
    scan = [a for a in alerts if a.key == "carteiras_sem_scan"]
    # 08:00 UTC = 06:00 BRT (horário de verão de 2001, UTC-2)
    assert [a.message for a in scan] == ["Carteiras sem scan desde 01/01/2001 06:00."]
    assert scan[0].action is not None and scan[0].action.label == "Ver conciliação"


def test_crypto_float_noise_is_not_divergence() -> None:
    """Revisão do Épico 7: 0,1 + 0,2 em float (duas carteiras) = 0,3 das operações."""
    app, origin = recon._crypto(0.3), recon._crypto(0.1 + 0.2)
    assert app == origin and calc.quantity_status("cripto", app, origin) == "conferido"
