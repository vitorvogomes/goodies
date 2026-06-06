"""§2.1: XIRR com preço parcial.

Com preços automáticos intermitentes (e ativos recém-comprados ainda sem cotação),
um ativo pode ter posição ABERTA e nenhum preço. Antes, suas compras entravam no
cashflow agregado como saída sem valor terminal → o XIRR consolidado/da categoria
despencava. Decisão: excluir do cashflow agregado os ativos com posição aberta e sem
preço. Posição FECHADA (net<=0) permanece — seus fluxos realizados são válidos.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from engines.portfolio import service

_T0 = date(2025, 6, 6)
_TODAY = date(2026, 6, 6)


async def _op(
    conn: Any,
    uid: str,
    sym: str,
    cat: str,
    tipo: str,
    qty: float,
    price: float,
    d: date,
) -> None:
    await conn.execute(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
        "tipo, quantidade, valor_unitario, data_operacao) "
        "VALUES ($1, 'Test', $2, $3, $4, $5, $6, $7)",
        uid,
        sym,
        cat,
        tipo,
        qty,
        price,
        d,
    )


@pytest.mark.asyncio
async def test_open_position_without_price_excluded(
    pool: Any, portfolio_user: dict
) -> None:
    uid = portfolio_user["user_id"]
    async with pool.acquire() as conn:
        # A: aberto, COM preço, ganho ~10% em 1 ano
        await _op(conn, uid, "GAINX", "Ações Nacionais", "compra", 100, 10.0, _T0)
        # B: aberto, SEM preço (cotação automática ainda não chegou)
        await _op(conn, uid, "NOPX", "Ações Nacionais", "compra", 50, 20.0, _T0)
        await service.upsert_price(conn, "GAINX", 11.0, source="b3", is_manual=False)
        result = await service.calculate_portfolio_xirr(conn, uid, today=_TODAY)

    # B não é valorável -> per-asset = None
    assert result["by_asset"]["NOPX"] is None
    # A rende ~10%
    assert result["by_asset"]["GAINX"] is not None
    assert abs(result["by_asset"]["GAINX"] - 0.10) < 0.02
    # consolidado ≈ A sozinho (B excluído), POSITIVO — não o negativo do bug
    assert result["consolidated"] is not None
    assert result["consolidated"] > 0
    assert abs(result["consolidated"] - 0.10) < 0.02
    # categoria idem (B excluído da agregação)
    assert abs(result["by_category"]["Ações Nacionais"] - 0.10) < 0.02


@pytest.mark.asyncio
async def test_closed_position_without_price_stays(
    pool: Any, portfolio_user: dict
) -> None:
    uid = portfolio_user["user_id"]
    async with pool.acquire() as conn:
        # comprado e VENDIDO por completo (net=0), sem preço atual: realizado ~20%
        await _op(conn, uid, "SOLDX", "Ações Nacionais", "compra", 100, 10.0, _T0)
        await _op(conn, uid, "SOLDX", "Ações Nacionais", "venda", 100, 12.0, _TODAY)
        result = await service.calculate_portfolio_xirr(conn, uid, today=_TODAY)

    # posição fechada sem preço NÃO é excluída — o XIRR realizado vale
    assert result["by_asset"]["SOLDX"] is not None
    assert abs(result["by_asset"]["SOLDX"] - 0.20) < 0.02
    assert result["consolidated"] is not None
    assert abs(result["consolidated"] - 0.20) < 0.02
