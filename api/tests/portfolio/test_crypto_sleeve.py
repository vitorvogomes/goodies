"""Tests do crypto sleeve (m4) — bridge ledger (custo BRL) ↔ carteiras (valor atual).

Cripto não vive em asset_operations; o sleeve cruza `transactions` (categorias cripto do
ledger) com `wallet_positions`+`defi_positions` valorados. Custo/XIRR só no nível do sleeve.
Tickers SINTÉTICOS de propósito (evita colisão com chaves cripto reais no Redis compartilhado).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
import pytest_asyncio

from engines.portfolio.crypto_sleeve import (
    calculate_crypto_sleeve,
    sleeve_cost_basis,
    sleeve_current_value,
)

_TODAY = date(2026, 6, 7)


async def _seed_account(conn: Any) -> uuid.UUID:
    return await conn.fetchval(
        "INSERT INTO accounts (name, type) VALUES ('Nubank Test', 'bank') RETURNING id"
    )


async def _tx(conn: Any, account_id: uuid.UUID, amount: float, category: str,
              when: date = _TODAY) -> None:
    await conn.execute(
        "INSERT INTO transactions (account_id, date, amount, category, kind) "
        "VALUES ($1, $2, $3, $4, 'investment')",
        account_id, when, amount, category,
    )


async def _price(conn: Any, ticker: str, price_brl: float) -> None:
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ($1, $2, 'coingecko', false) "
        "ON CONFLICT (ticker) DO UPDATE SET price_brl = EXCLUDED.price_brl",
        ticker, price_brl,
    )


async def _wallet(conn: Any, uid: str, chain: str, symbol: str, qty: float,
                  *, source: str = "etherscan", is_manual: bool = False,
                  address: str = "addr") -> None:
    await conn.execute(
        "INSERT INTO wallet_positions "
        "(user_id, chain, wallet_address, asset_symbol, quantity, source, is_manual) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
        uid, chain, address, symbol, qty, source, is_manual,
    )


async def _defi(conn: Any, uid: str, symbol: str, balance: float,
                *, protocol: str = "hylo", is_active: bool = True) -> None:
    await conn.execute(
        "INSERT INTO defi_positions (user_id, protocol, asset_symbol, balance, is_active) "
        "VALUES ($1, $2, $3, $4, $5)",
        uid, protocol, symbol, balance, is_active,
    )


@pytest_asyncio.fixture
async def sleeve_user(pool: Any) -> AsyncIterator[dict[str, Any]]:
    """Usuário fresco + conta; limpa todas as tabelas tocadas pelo sleeve no teardown."""
    uid = await _create_user(pool)
    async with pool.acquire() as conn:
        account_id = await _seed_account(conn)
    yield {"uid": str(uid), "account_id": account_id, "pool": pool}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", account_id)
        await conn.execute("DELETE FROM accounts WHERE id = $1", account_id)
        await conn.execute("DELETE FROM wallet_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM defi_positions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


async def _create_user(pool: Any) -> uuid.UUID:
    from auth.security import hash_password

    email = f"sleeve-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email, hash_password("sleeve-test"),
        )


class TestCostBasis:
    @pytest.mark.asyncio
    async def test_net_invested_from_ledger(self, sleeve_user: dict) -> None:
        """Saídas -1000/-200 + retorno +50 → custo 1200, retornado 50, líquido 1150."""
        pool, acc = sleeve_user["pool"], sleeve_user["account_id"]
        async with pool.acquire() as conn:
            await _tx(conn, acc, -1000.0, "Binance")
            await _tx(conn, acc, -200.0, "Cripto Diversos")
            await _tx(conn, acc, 50.0, "Cripto Nubnak")  # typo real da categoria
            cost = await sleeve_cost_basis(conn)
        assert abs(cost["cost_basis_brl"] - 1200.0) < 0.01
        assert abs(cost["returned_brl"] - 50.0) < 0.01
        assert abs(cost["net_invested_brl"] - 1150.0) < 0.01

    @pytest.mark.asyncio
    async def test_non_crypto_category_ignored(self, sleeve_user: dict) -> None:
        """Categoria fora do conjunto cripto não entra no custo do sleeve."""
        pool, acc = sleeve_user["pool"], sleeve_user["account_id"]
        async with pool.acquire() as conn:
            await _tx(conn, acc, -999.0, "Toro (B3)")
            cost = await sleeve_cost_basis(conn)
        assert cost["net_invested_brl"] == 0.0


class TestCurrentValue:
    @pytest.mark.asyncio
    async def test_wallet_plus_defi(self, sleeve_user: dict) -> None:
        pool, uid = sleeve_user["pool"], sleeve_user["uid"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _price(conn, "TKND", 2.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 3.0)  # 300
            await _defi(conn, uid, "TKND", 25.0)               # 50
            total, by_rail, stale = await sleeve_current_value(conn, uid)
        assert abs(total - 350.0) < 0.01
        assert stale is False
        assert abs(by_rail.get("ethereum", 0.0) - 300.0) < 0.01
        # rail DeFi por protocolo (helper usa protocol="hylo")
        assert abs(by_rail.get("hylo", 0.0) - 50.0) < 0.01

    @pytest.mark.asyncio
    async def test_dedup_manual_and_scanned(self, sleeve_user: dict) -> None:
        """Manual + escaneada do mesmo (chain, símbolo) → conta 1x (prefere a escaneada)."""
        pool, uid = sleeve_user["pool"], sleeve_user["uid"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _wallet(conn, uid, "liquid", "TKNA", 1.0, source="etherscan",
                          is_manual=False, address="scanned")
            await _wallet(conn, uid, "liquid", "TKNA", 1.0, source="manual",
                          is_manual=True, address="manual")
            total, _, _ = await sleeve_current_value(conn, uid)
        assert abs(total - 100.0) < 0.01  # não 200

    @pytest.mark.asyncio
    async def test_fail_soft_unpriced(self, sleeve_user: dict) -> None:
        """Sem preço → contribui 0 e marca stale_value, sem exceção (fail-soft)."""
        pool, uid = sleeve_user["pool"], sleeve_user["uid"]
        async with pool.acquire() as conn:
            await _wallet(conn, uid, "ethereum", "NOPRICE", 5.0)
            total, _, stale = await sleeve_current_value(conn, uid)
        assert total == 0.0
        assert stale is True


class TestSleeve:
    @pytest.mark.asyncio
    async def test_xirr_sign_gain(self, sleeve_user: dict) -> None:
        """Aporte -1000 há 365d + valor atual 1100 → XIRR ≈ +10%."""
        pool, uid, acc = sleeve_user["pool"], sleeve_user["uid"], sleeve_user["account_id"]
        async with pool.acquire() as conn:
            await _tx(conn, acc, -1000.0, "Binance", when=date(2025, 6, 7))
            await _price(conn, "TKNA", 1.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 1100.0)
            sleeve = await calculate_crypto_sleeve(conn, uid, today=_TODAY)
        assert abs(sleeve["current_value_brl"] - 1100.0) < 0.01
        assert abs(sleeve["net_invested_brl"] - 1000.0) < 0.01
        assert abs(sleeve["resultado"] - 100.0) < 0.01
        assert sleeve["xirr"] is not None
        assert abs(sleeve["xirr"] - 0.10) < 0.005

    @pytest.mark.asyncio
    async def test_xirr_sign_loss(self, sleeve_user: dict) -> None:
        """Aporte -1000 há 365d + valor atual 500 → XIRR negativo (≈ -50%)."""
        pool, uid, acc = sleeve_user["pool"], sleeve_user["uid"], sleeve_user["account_id"]
        async with pool.acquire() as conn:
            await _tx(conn, acc, -1000.0, "Binance", when=date(2025, 6, 7))
            await _price(conn, "TKNA", 1.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 500.0)
            sleeve = await calculate_crypto_sleeve(conn, uid, today=_TODAY)
        assert sleeve["xirr"] is not None
        assert sleeve["xirr"] < 0
        assert abs(sleeve["resultado"] - (-500.0)) < 0.01

    @pytest.mark.asyncio
    async def test_empty_sleeve(self, sleeve_user: dict) -> None:
        """Sem ledger cripto e sem carteiras → zeros, XIRR None, sem 5xx."""
        pool, uid = sleeve_user["pool"], sleeve_user["uid"]
        async with pool.acquire() as conn:
            sleeve = await calculate_crypto_sleeve(conn, uid, today=_TODAY)
        assert sleeve["current_value_brl"] == 0.0
        assert sleeve["net_invested_brl"] == 0.0
        assert sleeve["resultado"] == 0.0
        assert sleeve["xirr"] is None
