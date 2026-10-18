"""Story 10.6 — Operações (substituto da tela v1 /portfolio/history): filtros e o total de cada
operação calculado na API."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from engines.common.owner import get_owner_id
from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers


@pytest.mark.asyncio
async def test_operations_with_total(api, auth_headers, pool: Any) -> None:
    sym = f"ZO{uuid.uuid4().hex[:3].upper()}3"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, 'Ações Nacionais', "
            "'compra', 3, 10.155, '2097-02-03')",
            owner,
            sym,
        )
    try:
        r = await api.get(
            f"/api/v1/portfolio/operations?asset_symbol={sym.lower()}&tipo=compra",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) == 1 and rows[0]["total"] == 30.46  # 3 × 10,155 = 30,465 (meio-par)
        none = await api.get(
            f"/api/v1/portfolio/operations?asset_symbol={sym}&tipo=venda", headers=auth_headers
        )
        assert none.json() == []
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", sym)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{sym}")
