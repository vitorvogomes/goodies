"""Story 7.9 na base real: os eventos corporativos das movimentações B3 (bonificação e leilão de
fração) entram pelo `scripts.ops.import_b3_events`. Sem eles o app ficava com SOJA3 negativa depois
da venda total de jun/2026 (a bonificação de dez/2025 não existia) e divergia do consolidado B3
(AD-13). Rodar de novo não importa nada; aplicado, net e XIRR só mudam nos ativos com evento — a
correção explicada do gate m3 (P19)."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from engines.portfolio import calc
from scripts.ops.baseline import compute_baseline, load_pinned_baseline
from scripts.ops.import_b3_events import DEFAULT_DIR, import_events
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")
EVENT_ASSETS = {"SOJA3", "ITSA4"}


async def _state(dsn: str, evaluation: date) -> tuple[dict[str, Decimal], dict[str, Any]]:
    conn = await asyncpg.connect(dsn)
    try:
        quantities: dict[str, Decimal] = {}
        for symbol in EVENT_ASSETS:
            ops = await conn.fetch(
                "SELECT tipo, quantidade FROM asset_operations WHERE asset_symbol = $1", symbol
            )
            quantities[symbol] = calc.quantity(ops)
        baseline = json.loads(json.dumps(await compute_baseline(conn, evaluation)))
        return quantities, baseline
    finally:
        await conn.close()


def _changed(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


async def test_eventos_corporativos_corrigem_as_quantidades() -> None:
    import main  # noqa: F401

    base = load_pinned_baseline()
    if base is None or not any(DEFAULT_DIR.glob("movimentacao-*.xlsx")):
        require_or_skip("baseline fixado ou movimentações B3 locais ausentes")
        raise AssertionError("inalcançável")
    evaluation = date.fromisoformat(base["evaluation_date"])
    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        qty_before, before = await _state(dsn, evaluation)
        first = await import_events(dsn, DEFAULT_DIR, dry_run=False)
        again = await import_events(dsn, DEFAULT_DIR, dry_run=False)
        qty_after, after = await _state(dsn, evaluation)
    finally:
        await restore_dados()
    assert sum(r["imported"] for r in first) == 4  # 2 bonificações + 2 leilões de fração
    assert sum(r["imported"] for r in again) == 0  # idempotente
    assert qty_before["SOJA3"] < 0 and qty_after["SOJA3"] == 0  # venda total de jun/2026
    assert qty_after["ITSA4"] - qty_before["ITSA4"] >= 0
    assert _changed(before["aplicado"], after["aplicado"]) <= EVENT_ASSETS
    assert _changed(before["net"], after["net"]) <= EVENT_ASSETS
    assert _changed(before["xirr"]["by_asset"], after["xirr"]["by_asset"]) <= EVENT_ASSETS
    assert _changed(before["xirr"]["by_category"], after["xirr"]["by_category"]) <= {
        "Ações Nacionais"
    }
    # XIRR consolidado: +0,02 p.p. (6,77% → 6,79%), a correção explicada
    delta = after["xirr"]["consolidated"] - before["xirr"]["consolidated"]
    assert 0 < delta < 0.001
