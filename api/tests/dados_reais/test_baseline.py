"""Story 1.3 — regressão contra o baseline fixado (XIRR, aplicado, net, contagens, poupança).

Compara a base fixada MIGRADA ATÉ O HEAD com o arquivo gravado por `scripts.ops.baseline --salvar`
antes da v2, nunca com a data do dia nem com preço vivo: toda revisão de dado mantém estes números
(salvo os deltas esperados listados no teste da própria revisão).
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import date
from typing import Any

import asyncpg
import pytest

from engines.ledger.service import monthly_savings
from scripts.ops.baseline import compute_baseline, pinned_baseline, pinned_savings_v2
from tests.dados_reais.conftest import require_or_skip, restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _load() -> dict[str, Any]:
    path = pinned_baseline()
    if path is None or not path.is_file():
        require_or_skip("baseline fixado não encontrado em BACKUP_DIR/baseline")
        raise AssertionError("inalcançável")
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _close(a: Any, b: Any, path: str) -> None:
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: chaves diferentes {set(a) ^ set(b)}"
        for k in a:
            _close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, float) and isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{path}: {a} != {b}"
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


async def test_portfolio_e_caixa_iguais_ao_baseline() -> None:
    expected = _load()
    dados_dsn = await restore_dados()
    await asyncio.to_thread(alembic_upgrade, dados_dsn, "head")
    conn = await asyncpg.connect(dados_dsn)
    try:
        got = await compute_baseline(conn, date.fromisoformat(expected["evaluation_date"]))
    finally:
        await conn.close()
    got.pop("revision")
    expected.pop("revision")
    # Story 2.6 (ADR-015): resgate virou receita, então a taxa da view v1 muda; a taxa canônica é a
    # de `ledger/calc`, comparada com a lista v2 fixada.
    got.pop("savings_rate")
    expected.pop("savings_rate")
    pinned_v2 = pinned_savings_v2()
    if pinned_v2 is None:
        require_or_skip("lista v2 de poupança não fixada")
    conn2 = await asyncpg.connect(dados_dsn)
    try:
        v2 = await monthly_savings(conn2)
    finally:
        await conn2.close()
    assert {
        m.isoformat()[:7]: None if r is None else str(round(r * 100, 6)) for m, r in v2.items()
    } == pinned_v2
    try:
        _close(expected, json.loads(json.dumps(got)), "baseline")
    finally:
        await restore_dados()
