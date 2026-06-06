"""WI-2: registro das caixinhas/CDB Nubank como ativos de Renda Fixa (pré-m3).

Deriva operações datadas das transactions curadas, valora via rf_cdi (CDI const),
semeia preço is_manual. Testa idempotência, sinal (aporte/resgate), preço, e o CDB.
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
    seed_spec,
)

_TODAY = datetime.date(2026, 6, 6)
_CDI = 0.1065
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
    assert {"Nubank-SnowTrip", "Nubank-Turbo"} <= enabled
    # Reserva listada mas desabilitada (próxima a criar; zerada hoje).
    reserva = next(c for c in CAIXINHAS if c.symbol == "Nubank-Reserva")
    assert reserva.enabled is False
    assert CDB_GUANABARA.pct_cdi == 117.5


async def test_build_ops_derives_sign_and_dates(seed_env, pool):
    async with pool.acquire() as conn:
        ops = await build_caixinha_ops(conn, _TURBO)
    tipos = sorted(op["tipo"] for op in ops)
    assert tipos == ["aporte", "aporte", "resgate"]
    assert all(op["data_operacao"] == datetime.date(2025, 8, 1) for op in ops)
    assert all(op["external_id"].startswith("caixinha:Nubank-Turbo:") for op in ops)
    assert all(op["asset_category"] == "Renda Fixa" for op in ops)


async def test_seed_spec_creates_operations(seed_env, pool):
    async with pool.acquire() as conn:
        result = await seed_spec(conn, seed_env["user_id"], _TURBO, _TODAY, _CDI)
        n = await conn.fetchval(
            "SELECT count(*) FROM asset_operations WHERE user_id=$1 AND asset_symbol=$2",
            seed_env["user_id"],
            "Nubank-Turbo",
        )
    assert result["imported"] == 3
    assert result["net_principal"] == 2500.0  # 2000+1000-500
    assert n == 3


async def test_seed_idempotent(seed_env, pool):
    async with pool.acquire() as conn:
        await seed_spec(conn, seed_env["user_id"], _TURBO, _TODAY, _CDI)
        second = await seed_spec(conn, seed_env["user_id"], _TURBO, _TODAY, _CDI)
    assert second["imported"] == 0
    assert second["skipped"] == 3


async def test_price_is_manual_and_accrued(seed_env, pool):
    async with pool.acquire() as conn:
        await seed_spec(conn, seed_env["user_id"], _TURBO, _TODAY, _CDI)
        row = await conn.fetchrow(
            "SELECT price_brl, source, is_manual FROM asset_prices WHERE ticker=$1",
            "Nubank-Turbo",
        )
    assert row["is_manual"] is True
    assert row["source"] == "nubank-cdi"
    assert float(row["price_brl"]) > 1.0  # rendeu CDI sobre o principal


async def test_cdb_guanabara_two_aportes(seed_env, pool):
    async with pool.acquire() as conn:
        result = await seed_spec(conn, seed_env["user_id"], CDB_GUANABARA, _TODAY, _CDI)
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(quantidade),0) FROM asset_operations "
            "WHERE user_id=$1 AND asset_symbol='Guanabara-CDB'",
            seed_env["user_id"],
        )
    assert result["imported"] == 2
    assert float(total) == 200.0


async def test_no_price_when_value_negative(pool):
    """net>0 mas valor<0 (resgate antigo rende mais que aporte recente) → sem preço."""
    spec = CaixinhaSpec("Nubank-NegTest", "Nubank", 100.0, ("negtest",))
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1,'x') RETURNING id",
            f"neg-{uuid.uuid4().hex[:8]}@example.com",
        )
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1,'bank') RETURNING id",
            f"acc-{uuid.uuid4().hex[:8]}",
        )
        legs = [
            (Decimal("-100.00"), datetime.date(2026, 6, 1), "Aplicação RDB - negtest"),
            (Decimal("99.00"), datetime.date(2024, 6, 6), "Resgate RDB - negtest"),
        ]
        for amount, d, desc in legs:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, kind, "
                "description, external_id) VALUES "
                "($1,$2,$3,'Caixinha/RDB Nubank','investment',$4,$5)",
                acc,
                d,
                amount,
                desc,
                f"neg-{uuid.uuid4().hex}",
            )
        result = await seed_spec(conn, str(uid), spec, _TODAY, _CDI)
        price = await conn.fetchval("SELECT 1 FROM asset_prices WHERE ticker='Nubank-NegTest'")
        await conn.execute("DELETE FROM asset_operations WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM asset_prices WHERE ticker='Nubank-NegTest'")
        await conn.execute("DELETE FROM transactions WHERE account_id=$1", acc)
        await conn.execute("DELETE FROM accounts WHERE id=$1", acc)
        await conn.execute("DELETE FROM users WHERE id=$1", uid)
    assert result["net_principal"] == 1.0
    assert result["valor_atual"] < 0  # resgate acumulado > aporte
    assert result["preco_unit"] == 0.0
    assert price is None  # nenhum preço negativo semeado
