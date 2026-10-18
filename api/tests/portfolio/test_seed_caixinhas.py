"""Registro das caixinhas/CDB Nubank e a derivação das operações a partir das transações.

Os seeds (`seed_spec`, CDI constante, preço manual) saíram na Story 7.5: a derivação é dos hooks
(`derive_caixinha_ops`) e a valoração, do CDI publicado (Story 7.4).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest_asyncio

from engines.portfolio.caixinhas import (
    CAIXINHAS,
    CDB_GUANABARA,
    CaixinhaSpec,
    build_caixinha_ops,
)

_TURBO = CaixinhaSpec("Nubank-Turbo", "Nubank", 115.0, ("turbo",))


@pytest_asyncio.fixture
async def seed_env(pool):
    """Usuário + conta + transactions de caixinha; limpa tudo no teardown."""
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1,'x') RETURNING id",
            f"cx-{uuid.uuid4().hex[:8]}@example.com",
        )
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1,'bank') RETURNING id",
            f"acc-{uuid.uuid4().hex[:8]}",
        )
        # Turbo: 2 aportes (-2000, -1000) + 1 resgate (+500) = net 2500.
        # Guanabara: 2 aportes de -100.
        rows = [
            (
                "Caixinha/RDB Nubank",
                "investment",
                Decimal("-2000.00"),
                "Aplicação RDB - Caixinha Turbo",
            ),
            (
                "Caixinha/RDB Nubank",
                "investment",
                Decimal("-1000.00"),
                "Aplicação RDB - Caixinha Turbo",
            ),
            (
                "Caixinha/RDB Nubank",
                "investment",
                Decimal("500.00"),
                "Resgate RDB - Caixinha Turbo",
            ),
            (
                "Renda Fixa Nubank",
                "investment",
                Decimal("-100.00"),
                "Compra de CDB - Banco Guanabara",
            ),
            (
                "Renda Fixa Nubank",
                "investment",
                Decimal("-100.00"),
                "Compra de CDB - Banco Guanabara",
            ),
        ]
        for cat, kind, amount, desc in rows:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, kind, "
                "description, external_id) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                acc,
                datetime.date(2025, 8, 1),
                amount,
                cat,
                kind,
                desc,
                f"cxtx-{uuid.uuid4().hex}",
            )
    yield {"user_id": str(uid), "account_id": acc}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM asset_operations WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM asset_prices")
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


def test_registry_has_active_caixinhas():
    enabled = {c.symbol for c in CAIXINHAS if c.enabled}
    # Nu Reserva Imediata ativa desde jul/2026 (OFX de jul-out/2026); HotCash segue encerrada.
    assert {"Nubank-SnowTrip", "Nubank-Turbo", "Nubank-Reserva"} <= enabled
    hotcash = next(c for c in CAIXINHAS if c.symbol == "Nubank-HotCash")
    assert hotcash.enabled is False
    assert CDB_GUANABARA.pct_cdi == 117.5


async def test_build_ops_derives_sign_and_dates(seed_env, pool):
    async with pool.acquire() as conn:
        ops = await build_caixinha_ops(conn, _TURBO)
    tipos = sorted(op["tipo"] for op in ops)
    assert tipos == ["aporte", "aporte", "resgate"]
    assert all(op["data_operacao"] == datetime.date(2025, 8, 1) for op in ops)
    assert all(op["external_id"].startswith("caixinha:Nubank-Turbo:") for op in ops)
    assert all(op["asset_category"] == "Renda Fixa" for op in ops)
