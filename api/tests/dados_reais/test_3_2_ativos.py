"""Story 3.2 — revisão 0023 (ativos com chave única) sobre a base real.

restaura → `upgrade 0022` → mede → `upgrade 0023` → mede:
- toda operação e toda posição de carteira com `asset_id` (zero órfãs), pelo mapa das keys;
- contagem de operações, aplicado por classe e XIRR consolidado = antes (e = baseline);
- telas v1: posições e alocação com os mesmos números;
- metas por classe mapeadas para o enum da AD-11;
- idempotente: descer e subir de novo dá as mesmas keys e os mesmos vínculos.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import asyncpg
import pytest

from engines.portfolio import service as portfolio_service
from scripts._common import resolve_owner
from scripts.ops.baseline import compute_baseline, frozen_prices, load_pinned_baseline
from tests.dados_reais.conftest import require_or_skip, restore_dados
from tests.dados_reais.test_2_6_reclassificacoes import _downgrade
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")

EXPECTED_KEYS = {
    ("Ações Nacionais", "BBAS3"): "b3:BBAS3",
    ("ETFs", "ACWI11"): "b3:ACWI11",
    ("FIIs", "MXRF11"): "b3:MXRF11",
    ("Aposentadoria", "Tesouro IPCA+ 2032"): "td:IPCA+2032",
    ("Aposentadoria", "Tesouro IPCA+ com Juros Semestrais 2055"): "td:IPCA+JS2055",
    ("Aposentadoria", "Tesouro Prefixado 2032"): "td:PRE2032",
    ("Aposentadoria", "Tesouro Selic 2028"): "td:SELIC2028",
    ("Renda Fixa", "Nubank-Turbo"): "caixinha:turbo",
    ("Renda Fixa", "Nubank-SnowTrip"): "caixinha:snowtrip",
    ("Renda Fixa", "Flash-Debênture"): "debenture:flash",
    ("Renda Fixa", "Guanabara-CDB"): "cdb:guanabara",
}


async def _views(conn: asyncpg.Connection, evaluation: date) -> dict[str, Any]:
    owner = await resolve_owner(conn)
    assert owner is not None
    uid = str(owner["id"])
    with frozen_prices():
        positions = await portfolio_service.calculate_positions(conn, uid)
        allocation = await portfolio_service.calculate_allocation(conn, uid)
    return json.loads(
        json.dumps(
            {
                "positions": sorted(
                    (p["asset_symbol"], p.get("custo_total"), p.get("valor_atual"))
                    for p in positions
                ),
                "allocation": allocation,
                "ops": await conn.fetchval("SELECT count(*) FROM asset_operations"),
            },
            default=str,
        )
    )


async def _links(conn: asyncpg.Connection) -> dict[str, Any]:
    ops = await conn.fetch(
        "SELECT o.asset_category, o.asset_symbol, a.key FROM asset_operations o "
        "LEFT JOIN assets a ON a.id = o.asset_id GROUP BY 1, 2, 3"
    )
    wallets = await conn.fetch(
        "SELECT w.chain, w.asset_symbol, a.key FROM wallet_positions w "
        "LEFT JOIN assets a ON a.id = w.asset_id"
    )
    return {
        "ops": sorted((r["asset_category"], r["asset_symbol"], r["key"]) for r in ops),
        "wallets": sorted((r["chain"], r["asset_symbol"], r["key"]) for r in wallets),
        "keys": sorted(r["key"] for r in await conn.fetch("SELECT key FROM assets")),
    }


async def test_ativos_com_chave_unica() -> None:
    base = load_pinned_baseline()
    if base is None:
        require_or_skip("baseline fixado não encontrado")
        raise AssertionError("inalcançável")
    evaluation = date.fromisoformat(base["evaluation_date"])
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "0022_alert_dismissals")
        conn = await asyncpg.connect(dsn)
        try:
            before = await _views(conn, evaluation)
        finally:
            await conn.close()

        await asyncio.to_thread(alembic_upgrade, dsn, "0023_assets")
        conn = await asyncpg.connect(dsn)
        try:
            links = await _links(conn)
            assert all(k is not None for *_, k in links["ops"]), "operação sem ativo"
            assert all(k is not None for *_, k in links["wallets"]), "posição sem ativo"
            by_label = {(c, s): k for c, s, k in links["ops"]}
            for label, key in EXPECTED_KEYS.items():
                assert by_label[label] == key
            wallet_keys = {(ch, s): k for ch, s, k in links["wallets"]}
            assert wallet_keys[("hyperliquid", "HYPE")] == wallet_keys[("hyperevm", "HYPE")]
            assert wallet_keys[("arbitrum", "ETH")] == wallet_keys[("ethereum", "ETH")]
            assert wallet_keys[("bitcoin", "BTC")] == "crypto:BTC"
            classes = dict(
                await conn.fetch("SELECT category, class FROM portfolio_targets ORDER BY 1")
            )
            assert classes == {
                "Ações Nacionais": "acoes_br",
                "Aposentadoria": "aposentadoria",
                "Cripto": "cripto",
                "ETFs": "etfs",
                "FIIs": "fiis",
                "Renda Fixa": "renda_fixa",
            }
            assert await _views(conn, evaluation) == before
            got = json.loads(json.dumps(await compute_baseline(conn, evaluation)))
            for k in ("xirr", "aplicado", "net", "counts"):
                assert got[k] == base[k], k
            with pytest.raises(asyncpg.RaiseError):
                await conn.execute("UPDATE assets SET key = 'b3:OUTRO' WHERE key = 'b3:BBAS3'")
        finally:
            await conn.close()

        await asyncio.to_thread(_downgrade, dsn, "0022_alert_dismissals")
        await asyncio.to_thread(alembic_upgrade, dsn, "0023_assets")
        conn = await asyncpg.connect(dsn)
        try:
            assert await _links(conn) == links
        finally:
            await conn.close()
    finally:
        await restore_dados()
