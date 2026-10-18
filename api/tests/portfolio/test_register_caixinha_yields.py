"""Registro de rendimento realizado das caixinhas (juros embutidos nos resgates).

Reclassificação XIRR-neutra resgate→juros: corrige o principal subcontado (Turbo) e
registra o rendimento das encerradas num bucket. Idempotente.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio

from scripts.oneoff.register_caixinha_yields import (
    _CLOSED_MARKER,
    _CLOSED_SYMBOL,
    _NET_QTY_SQL,
    _TURBO_MARKER,
    _TURBO_SYMBOL,
    register_closed_yield,
    register_turbo_yield,
)


@pytest_asyncio.fixture
async def yield_env(pool: Any) -> Any:
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1,'x') RETURNING id",
            f"yld-{uuid.uuid4().hex[:8]}@example.com",
        )
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1,'bank') RETURNING id",
            f"acc-{uuid.uuid4().hex[:8]}",
        )
        # limpa os símbolos-alvo (outros testes podem ter deixado)
        await conn.execute(
            "DELETE FROM asset_operations WHERE asset_symbol = ANY($1::text[])",
            [_TURBO_SYMBOL, _CLOSED_SYMBOL],
        )
        # Turbo: aportes 3000 + resgate 1000 (o "maior") -> net 2000
        for q, tipo in ((2000.0, "aporte"), (1000.0, "aporte"), (1000.0, "resgate")):
            await conn.execute(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
                "asset_category, tipo, quantidade, valor_unitario, data_operacao, external_id) "
                "VALUES ($1,'Nubank',$2,'Renda Fixa',$3,$4,1.0,'2025-08-01',$5)",
                uid,
                _TURBO_SYMBOL,
                tipo,
                q,
                f"t-{uuid.uuid4().hex}",
            )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ($1, 1.05, 'manual', true) ON CONFLICT (ticker) DO UPDATE "
            "SET price_brl = 1.05",
            _TURBO_SYMBOL,
        )
        # Encerradas: aporte -200 + resgate +250 (resgatou mais -> rendimento 50)
        for amt, desc in (
            (Decimal("-200.00"), "Aplicação RDB - Caixinha Extra"),
            (Decimal("250.00"), "Resgate RDB - Caixinha Extra"),
        ):
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, kind, "
                "description, external_id) VALUES ($1,'2025-09-01',$2,"
                "'Caixinha/RDB Nubank','investment',$3,$4)",
                acc,
                amt,
                desc,
                f"cx-{uuid.uuid4().hex}",
            )
    yield {"user_id": str(uid), "account_id": acc}
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM asset_operations WHERE asset_symbol = ANY($1::text[])",
            [_TURBO_SYMBOL, _CLOSED_SYMBOL],
        )
        await conn.execute(
            "DELETE FROM asset_prices WHERE ticker = ANY($1::text[])",
            [_TURBO_SYMBOL, _CLOSED_SYMBOL],
        )
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


async def _net(conn: Any, sym: str) -> float:
    return float(await conn.fetchval(_NET_QTY_SQL, sym))


@pytest.mark.asyncio
async def test_turbo_reclassifies_resgate_to_juros(yield_env: Any, pool: Any) -> None:
    async with pool.acquire() as conn:
        assert await _net(conn, _TURBO_SYMBOL) == 2000.0  # net antes
        res = await register_turbo_yield(conn, target_principal=2100.0, apply=True)
        assert res["status"] == "applied"
        assert res["realized"] == 100.0  # 2100 - 2000
        # net sobe p/ o principal real
        assert await _net(conn, _TURBO_SYMBOL) == 2100.0
        # juros registrado (op marcador)
        juros = await conn.fetchrow(
            "SELECT quantidade, tipo FROM asset_operations WHERE external_id = $1",
            _TURBO_MARKER,
        )
        assert juros["tipo"] == "juros"
        assert float(juros["quantidade"]) == 100.0
        # maior resgate reduzido (1000 -> 900)
        resg = await conn.fetchval(
            "SELECT quantidade FROM asset_operations WHERE asset_symbol = $1 AND tipo = 'resgate'",
            _TURBO_SYMBOL,
        )
        assert float(resg) == 900.0
        # preço recalibrado p/ preservar o valor (2000*1.05 = 2100 -> price 1.00)
        price = await conn.fetchval(
            "SELECT price_brl FROM asset_prices WHERE ticker = $1", _TURBO_SYMBOL
        )
        assert abs(float(price) - 1.00) < 1e-6


@pytest.mark.asyncio
async def test_turbo_is_idempotent(yield_env: Any, pool: Any) -> None:
    async with pool.acquire() as conn:
        await register_turbo_yield(conn, target_principal=2100.0, apply=True)
        again = await register_turbo_yield(conn, target_principal=2100.0, apply=True)
        assert again["status"] == "already_done"
        assert await _net(conn, _TURBO_SYMBOL) == 2100.0  # não aplica 2x
        n = await conn.fetchval(
            "SELECT count(*) FROM asset_operations WHERE external_id = $1", _TURBO_MARKER
        )
        assert n == 1


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(yield_env: Any, pool: Any) -> None:
    async with pool.acquire() as conn:
        res = await register_turbo_yield(conn, target_principal=2100.0, apply=False)
        assert res["status"] == "dry-run"
        assert res["realized"] == 100.0
        assert await _net(conn, _TURBO_SYMBOL) == 2000.0  # inalterado
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM asset_operations WHERE external_id = $1", _TURBO_MARKER
            )
            == 0
        )


@pytest.mark.asyncio
async def test_closed_yield_bucket(yield_env: Any, pool: Any) -> None:
    async with pool.acquire() as conn:
        res = await register_closed_yield(conn, apply=True)
        assert res["status"] == "applied"
        assert res["realized"] == 50.0  # 250 resgate - 200 aporte
        op = await conn.fetchrow(
            "SELECT asset_symbol, tipo, quantidade, data_operacao "
            "FROM asset_operations WHERE external_id = $1",
            _CLOSED_MARKER,
        )
        assert op["asset_symbol"] == _CLOSED_SYMBOL
        assert op["tipo"] == "juros"
        assert float(op["quantidade"]) == 50.0
        assert op["data_operacao"] == datetime.date(2025, 9, 1)  # MAX(date) das encerradas
        # bucket não vira posição (net_quantity = 0, só juros)
        assert await _net(conn, _CLOSED_SYMBOL) == 0.0


@pytest.mark.asyncio
async def test_closed_excludes_active_caixinhas(yield_env: Any, pool: Any) -> None:
    """O bucket casa por exclusão de snow/turbo/guanabara — não captura as ativas."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category, kind, "
            "description, external_id) VALUES ($1,'2025-09-02',-9999,"
            "'Caixinha/RDB Nubank','investment','Aplicação RDB - Caixinha Turbo',$2)",
            yield_env["account_id"],
            f"cx-{uuid.uuid4().hex}",
        )
        res = await register_closed_yield(conn, apply=True)
        assert res["realized"] == 50.0  # ignora a tx do Turbo (excluída)
