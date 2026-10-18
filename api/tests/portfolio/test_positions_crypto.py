"""Cripto como BLOCO em Posições → Alocação (m4).

Cripto não tem a granularidade fiel de B3/RF (custo por ativo só parcialmente recuperável —
`docs/15`). Em Posições aparece como UMA linha-bloco (sleeve: investido vs valor atual); o
detalhe por moeda/chain vive nas Carteiras Cripto. A Alocação soma o valor do bloco como
categoria Cripto. Tickers sintéticos (serviço direto: as rotas v1 saíram na Story 10.6).
"""

from __future__ import annotations

from typing import Any

import pytest

from engines.portfolio import service
from tests.portfolio.conftest import run


async def _price(conn: Any, ticker: str, brl: float) -> None:
    await conn.execute(
        "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
        "VALUES ($1, $2, 'coingecko', false)",
        ticker,
        brl,
    )


async def _wallet(conn: Any, uid: str, chain: str, sym: str, qty: float) -> None:
    await conn.execute(
        "INSERT INTO wallet_positions "
        "(user_id, chain, wallet_address, asset_symbol, quantity, source, is_manual) "
        "VALUES ($1, $2, $3, $4, $5, 'etherscan', false)",
        uid,
        chain,
        f"addr-{chain}",
        sym,
        qty,
    )


async def _defi(conn: Any, uid: str, sym: str, bal: float) -> None:
    await conn.execute(
        "INSERT INTO defi_positions (user_id, protocol, asset_symbol, balance, is_active) "
        "VALUES ($1, 'hylo', $2, $3, true)",
        uid,
        sym,
        bal,
    )


class TestCryptoBucket:
    @pytest.mark.asyncio
    async def test_single_bucket_row(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        """Carteira + DeFi → UMA linha 'Cripto' (is_bucket); valor = soma; sem ledger custo None."""
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _price(conn, "TKND", 4.0)
            await _wallet(conn, uid, "binance", "TKNA", 2.0)  # 200
            await _defi(conn, uid, "TKND", 25.0)  # 100
        data = await run(pool, service.calculate_positions, uid)
        crypto = [p for p in data if p["asset_category"] == "Cripto"]
        assert len(crypto) == 1
        bucket = crypto[0]
        assert bucket["asset_symbol"] == "Cripto"
        assert bucket["is_bucket"] is True
        assert bucket["custody"] is None
        assert bucket["quantidade_net"] is None
        assert bucket["preco_medio"] is None
        assert abs(float(bucket["valor_atual"]) - 300.0) < 0.01
        assert bucket["custo_total"] is None  # sem aporte no ledger
        assert bucket["resultado"] is None

    @pytest.mark.asyncio
    async def test_no_crypto_no_bucket(self, pool: Any, portfolio_user: dict) -> None:
        data = await run(pool, service.calculate_positions, portfolio_user["user_id"])
        assert not [p for p in data if p["asset_category"] == "Cripto"]

    @pytest.mark.asyncio
    async def test_crypto_asset_operation_is_not_double_counted(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        """Achado C6: uma op de categoria Cripto em asset_operations NÃO pode virar linha
        per-ativo (o sleeve/bloco já valora cripto pelas carteiras) — senão conta 2x."""
        # ticker sintético (não-BTC) p/ não colidir com preço cacheado no Redis de outro teste
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKCRP", 300000.0)
            await _wallet(conn, uid, "binance", "TKCRP", 0.01)  # bloco = 3000
            # op Cripto registrada em asset_operations
            await conn.execute(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, "
                "asset_category, tipo, quantidade, valor_unitario, data_operacao) "
                "VALUES ($1, 'Binance', 'TKCRP', 'Cripto', 'compra', 0.01, 200000.0, "
                "'2026-01-02')",
                uid,
            )
        data = await run(pool, service.calculate_positions, uid)
        crypto = [p for p in data if p["asset_category"] == "Cripto"]
        assert len(crypto) == 1  # só o bloco — NÃO uma linha TKCRP per-ativo
        assert crypto[0]["is_bucket"] is True
        # o bloco vale o saldo da carteira (3000), não soma a op (que viraria +2000 custo)
        assert abs(float(crypto[0]["valor_atual"]) - 3000.0) < 0.01


class TestAllocationCryptoFold:
    @pytest.mark.asyncio
    async def test_allocation_includes_cripto(
        self, pool: Any, portfolio_user: dict
    ) -> None:
        uid = portfolio_user["user_id"]
        async with pool.acquire() as conn:
            await _price(conn, "TKNA", 100.0)
            await _wallet(conn, uid, "ethereum", "TKNA", 1.0)  # 100
        data = await run(pool, service.calculate_allocation, uid)
        cats = {c["category"]: c for c in data["categories"]}
        assert "Cripto" in cats
        assert cats["Cripto"]["valor_atual"] > 0
        assert cats["Cripto"]["pct_meta"] == 5.0
        assert cats["Cripto"]["desvio_pp"] is not None

