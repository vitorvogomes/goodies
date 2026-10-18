"""Pedido de 18/10/2026: os avisos do fechamento dizem o que acontece com o mês e não aparecem
quando não se aplicam — sem posição na B3 no fim do mês, nada de "Consolidado não importado"; antes
do primeiro scan das carteiras, o cripto vale o aplicado (informativo, não é pendência)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.common.owner import get_owner_id
from engines.portfolio import service as portfolio
from engines.wallet import service as wallet


@pytest.mark.asyncio
async def test_no_b3_position_no_consolidado_warning(pool: Any) -> None:
    async with pool.acquire() as conn:
        codes = [c["code"] for c in await portfolio.close_checks(conn, date(1990, 1, 1))]
    assert "consolidado_ausente" not in codes


@pytest.mark.asyncio
async def test_b3_position_without_consolidado_explains(pool: Any) -> None:
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'Toro', 'ZZCK3', "
            "'Ações Nacionais', 'compra', 1, 10, '2093-05-10')",
            owner,
        )
        try:
            checks = await portfolio.close_checks(conn, date(2093, 5, 1))
        finally:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = 'ZZCK3'")
            await conn.execute("DELETE FROM assets WHERE price_ref = 'ZZCK3'")
    found = next(c for c in checks if c["code"] == "consolidado_ausente")
    assert found["kind"] == "confirma" and "histórico de preço" in found["message"]


@pytest.mark.asyncio
async def test_crypto_check_before_first_scan_is_info(pool: Any) -> None:
    async with pool.acquire() as conn:
        first = await conn.fetchval("SELECT min(ref_date) FROM wallet_position_history")
        account = await conn.fetchval("SELECT id FROM accounts LIMIT 1")
        tx = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, description) "
            "VALUES ($1, '1991-03-05', -100, (SELECT id FROM categories "
            "WHERE key = 'invest:cripto_diversos'), 'investment', 'zz cripto') RETURNING id",
            account,
        )
        try:
            before = await wallet.close_checks(conn, date(1991, 3, 1))
            none = await wallet.close_checks(conn, date(1990, 1, 1))  # sem cripto ainda
        finally:
            await conn.execute("DELETE FROM transactions WHERE id = $1", tx)
    assert none == []
    assert [c["kind"] for c in before] == ["info"]
    assert "aplicado" in before[0]["message"]
    if first is not None:
        assert f"{first:%d/%m/%Y}" in before[0]["message"]


@pytest.mark.asyncio
async def test_crypto_check_after_first_scan_names_the_last_scan(pool: Any) -> None:
    async with pool.acquire() as conn:
        asset = await conn.fetchval("SELECT id FROM assets WHERE class = 'cripto' LIMIT 1")
        await conn.execute(
            "INSERT INTO wallet_position_history (asset_id, ref_date, quantity, chain, "
            "wallet_address, source) VALUES ($1, '1992-02-10', 1, 'zz', 'zz', 'teste')",
            asset,
        )
        try:
            checks = await wallet.close_checks(conn, date(1992, 4, 1))
        finally:
            await conn.execute("DELETE FROM wallet_position_history WHERE chain = 'zz'")
    assert [c["kind"] for c in checks] == ["confirma"]
    assert "10/02/1992" in checks[0]["message"]
