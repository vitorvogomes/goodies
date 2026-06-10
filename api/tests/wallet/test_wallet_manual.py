"""Posições manuais em wallet_positions (Liquid confidencial, não escaneável) — m4."""
from __future__ import annotations

from typing import Any

import pytest

from engines.market.fetchers.wallets.base import WalletBalance
from engines.wallet import service
from workers.wallet_workers import run_wallet_scan


class _FakeFetcher:
    def __init__(self, balances: list[WalletBalance]) -> None:
        self._b = balances

    async def fetch(self) -> list[WalletBalance]:
        return self._b


@pytest.mark.asyncio
async def test_create_manual_position_appears_in_list(api: Any, wallet_user: dict) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.25},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 200
    pos = await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])
    rows = {p["asset_symbol"]: p for p in pos.json()}
    assert rows["L-BTC"]["is_manual"] is True
    assert rows["L-BTC"]["quantity"] == pytest.approx(0.25)
    assert rows["L-BTC"]["chain"] == "liquid"


@pytest.mark.asyncio
async def test_manual_upsert_is_idempotent(api: Any, wallet_user: dict, pool: Any) -> None:
    uid = wallet_user["user_id"]
    for qty in (1.0, 2.5):
        await api.post(
            "/api/v1/wallets/positions/manual",
            json={"chain": "liquid", "asset_symbol": "L-USDT", "quantity": qty},
            headers=wallet_user["headers"],
        )
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM wallet_positions WHERE user_id = $1 "
            "AND asset_symbol = 'L-USDT'",
            uid,
        )
        q = await conn.fetchval(
            "SELECT quantity FROM wallet_positions WHERE user_id = $1 "
            "AND asset_symbol = 'L-USDT'",
            uid,
        )
    assert n == 1  # upsert: uma linha só
    assert float(q) == pytest.approx(2.5)  # última quantidade vence


@pytest.mark.asyncio
async def test_delete_manual_position(api: Any, wallet_user: dict) -> None:
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.1},
        headers=wallet_user["headers"],
    )
    d = await api.delete(
        "/api/v1/wallets/positions/manual/liquid/L-BTC", headers=wallet_user["headers"]
    )
    assert d.status_code == 204
    d2 = await api.delete(
        "/api/v1/wallets/positions/manual/liquid/L-BTC", headers=wallet_user["headers"]
    )
    assert d2.status_code == 404  # já removida


@pytest.mark.asyncio
async def test_sweep_preserves_manual(api: Any, wallet_user: dict, pool: Any) -> None:
    # posição manual de Liquid sobrevive a um scan que cobre o source 'liquid'
    uid = wallet_user["user_id"]
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.3},
        headers=wallet_user["headers"],
    )
    fetcher = _FakeFetcher([WalletBalance("liquid", "lqADDR", "L-OTHER", 1.0, "liquid")])
    await run_wallet_scan(pool, uid, fetchers=[fetcher])
    async with pool.acquire() as conn:
        rows = [
            r["asset_symbol"]
            for r in await conn.fetch(
                "SELECT asset_symbol FROM wallet_positions WHERE user_id = $1 "
                "ORDER BY asset_symbol",
                uid,
            )
        ]
    assert "L-BTC" in rows  # manual preservada (não varrida)
    assert "L-OTHER" in rows  # escaneada gravada


@pytest.mark.asyncio
async def test_manual_position_rejects_negative(api: Any, wallet_user: dict) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": -1},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_manual_requires_auth(api: Any) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.1},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_manual_rejected_when_scanned_exists(api: Any, wallet_user: dict, pool: Any) -> None:
    # já existe uma posição ESCANEADA do mesmo (chain, ativo) → manual viraria contagem dupla
    uid = wallet_user["user_id"]
    async with pool.acquire() as conn:
        await service.upsert_wallet_position(
            conn, uid, WalletBalance("solana", "solREAL", "MNL_SOL", 2.0, "solana")
        )
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "solana", "asset_symbol": "MNL_SOL", "quantity": 1.0},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_and_reconcile_prefer_scanned_over_manual(
    api: Any, wallet_user: dict, pool: Any
) -> None:
    # manual criada primeiro; depois um scan acha o mesmo (chain, ativo) num endereço real
    uid = wallet_user["user_id"]
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "solana", "asset_symbol": "MNL_DUP", "quantity": 5.0},
        headers=wallet_user["headers"],
    )
    async with pool.acquire() as conn:
        await service.upsert_wallet_position(
            conn, uid, WalletBalance("solana", "solREAL", "MNL_DUP", 2.0, "solana")
        )
    # list: aparece uma vez só, a ESCANEADA (não soma manual+escaneada)
    pos = (await api.get("/api/v1/wallets/positions", headers=wallet_user["headers"])).json()
    dup = [p for p in pos if p["asset_symbol"] == "MNL_DUP"]
    assert len(dup) == 1
    assert dup[0]["is_manual"] is False
    assert dup[0]["quantity"] == pytest.approx(2.0)
    # reconcile: escaneado contado uma vez (2.0), não 7.0
    rec = (await api.get("/api/v1/wallets/reconciliation", headers=wallet_user["headers"])).json()
    by = {r["asset_symbol"]: r for r in rec}
    assert by["MNL_DUP"]["scanned_quantity"] == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_manual_rejects_whitespace_symbol(api: Any, wallet_user: dict) -> None:
    r = await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "   ", "quantity": 0.1},
        headers=wallet_user["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_manual_write_invalidates_xirr_cache(
    api: Any, wallet_user: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Achado C7: a posição manual alimenta o XIRR consolidado via sleeve; criar/
    apagar precisa invalidar o cache de XIRR (1h), senão o dashboard fica incoerente."""
    calls: list[str] = []

    async def spy(uid: str) -> None:
        calls.append(uid)

    monkeypatch.setattr("engines.wallet.router.invalidate_xirr_cache", spy)
    await api.post(
        "/api/v1/wallets/positions/manual",
        json={"chain": "liquid", "asset_symbol": "L-BTC", "quantity": 0.2},
        headers=wallet_user["headers"],
    )
    assert calls == [wallet_user["user_id"]]
    calls.clear()
    await api.delete(
        "/api/v1/wallets/positions/manual/liquid/L-BTC", headers=wallet_user["headers"]
    )
    assert calls == [wallet_user["user_id"]]
