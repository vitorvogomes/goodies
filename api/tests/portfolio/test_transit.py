"""F — reconciliação de trânsito por trilho (saiu ledger vs aplicado asset_operations)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

from engines.portfolio.transit import calculate_transit


async def _ins_op(
    conn: Any, uid: str, broker: str, sym: str, cat: str, tipo: str,
    qty: str, vu: str, ext: str,
) -> None:
    await conn.execute(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
        "tipo, quantidade, valor_unitario, data_operacao, external_id) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        uid, broker, sym, cat, tipo, Decimal(qty), Decimal(vu), date(2026, 6, 1), ext,
    )


async def _ins_tx(conn: Any, acc: Any, amount: str, category: str, ext: str) -> None:
    await conn.execute(
        "INSERT INTO transactions (account_id, date, amount, category, kind, "
        "description, external_id) VALUES ($1,$2,$3,$4,'investment','x',$5)",
        acc, date(2026, 6, 1), Decimal(amount), category, ext,
    )


class TestTransit:
    @pytest.mark.asyncio
    async def test_b3_rail_saiu_aplicado_em_transito(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")  # estado global limpo
            acc = await conn.fetchval(
                "INSERT INTO accounts (name, type) VALUES ('tr', 'bank') RETURNING id"
            )
            await _ins_tx(conn, acc, "-1000", "Toro (B3)", "tx-b3")  # saiu 1000
            await _ins_op(
                conn, uid, "Toro/B3", "BBAS3", "Ações Nacionais", "compra", "8", "100", "op-c"
            )
            await _ins_op(
                conn, uid, "Toro/B3", "BBAS3", "Ações Nacionais", "venda", "1", "50", "op-v"
            )
            res = await calculate_transit(conn, uid)
        b3 = next(r for r in res["rails"] if r["rail"] == "B3 (corretoras)")
        assert b3["saiu_brl"] == 1000.0
        assert b3["aplicado_brl"] == 750.0  # 800 compra - 50 venda
        assert b3["em_transito_brl"] == 250.0

    @pytest.mark.asyncio
    async def test_rf_nubank_vs_flash_disambiguated_by_broker(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
            acc = await conn.fetchval(
                "INSERT INTO accounts (name, type) VALUES ('tr2', 'bank') RETURNING id"
            )
            await _ins_tx(conn, acc, "-500", "Flash Capital debêntures", "tx-flash")
            # Flash e Nubank RF têm a MESMA categoria ('Renda Fixa'); o broker desambigua
            await _ins_op(
                conn, uid, "Flash", "Flash-Deb", "Renda Fixa", "compra", "1", "500", "op-f"
            )
            await _ins_op(
                conn, uid, "Nubank", "Nubank-Turbo", "Renda Fixa", "compra", "1", "999", "op-n"
            )
            res = await calculate_transit(conn, uid)
        flash = next(r for r in res["rails"] if r["rail"] == "Debêntures Flash")
        assert flash["saiu_brl"] == 500.0
        assert flash["aplicado_brl"] == 500.0  # só o broker Flash, não o Nubank (999)
        assert flash["em_transito_brl"] == 0.0

    @pytest.mark.asyncio
    async def test_b3_dividends_become_broker_cash_not_transit(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        """Dividendos/JCP creditados na corretora são CAIXA parado lá, não trânsito.
        caixa_corretora = em_transito + dividendos + juros (≈ saldo na Toro)."""
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
            acc = await conn.fetchval(
                "INSERT INTO accounts (name, type) VALUES ('trd', 'bank') RETURNING id"
            )
            await _ins_tx(conn, acc, "-1000", "Toro (B3)", "tx-b3d")  # saiu 1000
            await _ins_op(
                conn, uid, "Toro/B3", "BBAS3", "Ações Nacionais", "compra", "8", "100", "op-cd"
            )  # aplicado 800 → em_transito 200
            await _ins_op(
                conn, uid, "Toro/B3", "BBAS3", "Ações Nacionais", "dividendo", "1", "30", "op-d"
            )
            await _ins_op(
                conn, uid, "Toro/B3", "PETR4", "Ações Nacionais", "juros", "1", "20", "op-j"
            )
            res = await calculate_transit(conn, uid)
        b3 = next(r for r in res["rails"] if r["rail"] == "B3 (corretoras)")
        assert b3["aplicado_brl"] == 800.0  # dividendo/juros NÃO entram no aplicado
        assert b3["em_transito_brl"] == 200.0
        assert b3["dividendos_juros_brl"] == 50.0
        assert b3["caixa_corretora_brl"] == 250.0  # 200 trânsito + 50 proventos
        assert b3["status"] == "pending"

    @pytest.mark.asyncio
    async def test_negative_transit_is_rendimento_realizado(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        """aplicado > saiu (ex.: caixinha encerrada que rendeu) → NÃO é 'conciliado':
        é rendimento realizado. O status vem do backend, não do front."""
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
            acc = await conn.fetchval(
                "INSERT INTO accounts (name, type) VALUES ('trn', 'bank') RETURNING id"
            )
            await _ins_tx(conn, acc, "-100", "Tesouro Direto Nubank", "tx-td")  # saiu 100
            await _ins_op(
                conn, uid, "NU", "Tesouro X", "Aposentadoria", "aporte", "1", "150", "op-td"
            )  # virou 150 (rendeu) → em_transito -50
            res = await calculate_transit(conn, uid)
        td = next(r for r in res["rails"] if r["rail"] == "Tesouro Direto")
        assert td["em_transito_brl"] == -50.0
        assert td["status"] == "rendimento_realizado"
        assert td["caixa_corretora_brl"] is None  # sem proventos no trilho

    @pytest.mark.asyncio
    async def test_reconciled_status_within_tolerance(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
            acc = await conn.fetchval(
                "INSERT INTO accounts (name, type) VALUES ('trc', 'bank') RETURNING id"
            )
            await _ins_tx(conn, acc, "-500", "Flash Capital debêntures", "tx-fl2")
            await _ins_op(
                conn, uid, "Flash", "Flash-Deb", "Renda Fixa", "compra", "1", "500", "op-fl2"
            )
            res = await calculate_transit(conn, uid)
        flash = next(r for r in res["rails"] if r["rail"] == "Debêntures Flash")
        assert flash["em_transito_brl"] == 0.0
        assert flash["status"] == "reconciled"

    @pytest.mark.asyncio
    async def test_crypto_block_from_sleeve(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
            res = await calculate_transit(conn, uid)
        assert res["crypto"]["net_invested_brl"] == 0.0
        assert res["crypto"]["current_value_brl"] == 0.0


class TestTransitEndpoint:
    @pytest.mark.asyncio
    async def test_endpoint_shape(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM transactions")
        resp = await api.get(
            "/api/v1/portfolio/transit", headers=portfolio_user["headers"]
        )
        assert resp.status_code == 200
        body = resp.json()
        assert any(r["rail"] == "B3 (corretoras)" for r in body["rails"])
        assert "net_invested_brl" in body["crypto"]
