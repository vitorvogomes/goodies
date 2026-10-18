"""Story 8.3 — alocação × meta: a base exclui os ativos de objetivos (bloco "Objetivos", ainda no
patrimônio); classe e ativo mostram alocação, meta, banda e desvio em p.p.; fora da banda vira o
aviso "{Classe} em {x,xx}%, meta {y,yy}% ± {b} p.p." (Ver aportes)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.common.alerts import AlertContext
from engines.common.dates import today_brt
from engines.common.models import Valued
from engines.common.owner import get_owner_id
from engines.planning import allocation, calc
from engines.portfolio.positions import GOALS_BLOCK, PositionAsset, PositionClass

D = Decimal


def test_shares_and_band() -> None:
    shares = calc.allocation_shares({"a": D(600), "b": D(400)}, {"a": D(50), "b": D(50)})
    assert (shares["a"].atual, shares["a"].desvio) == (D(60), D(10))
    assert calc.out_of_band(D(10), D(5)) and not calc.out_of_band(D(-4), D(5))
    lone = calc.allocation_shares({"a": D(1)}, {})
    assert lone["a"].meta is None and lone["a"].desvio is None
    assert calc.allocation_shares({"a": D(1)}, {"a": D(100), "c": D(0)})["c"].atual == D(0)


def _asset(symbol: str, value: str, asset_id: str | None = None) -> PositionAsset:
    return PositionAsset(
        symbol=symbol,
        asset_id=asset_id,
        aplicado=D(value),
        valor=Valued[Decimal](value=D(value)),
        resultado=D(0),
    )


def _cls(key: str, assets: list[PositionAsset]) -> PositionClass:
    return PositionClass(
        key=key,
        label=key,
        is_bucket=False,
        aplicado=D(0),
        valor=sum((a.valor.value or D(0) for a in assets), D(0)),
        resultado=D(0),
        assets=assets,
    )


async def _targets(conn: Any, month: date) -> None:
    owner = await get_owner_id(conn)
    await conn.execute(
        "UPDATE portfolio_targets SET valid_to = $2 WHERE user_id = $1::uuid AND valid_to IS NULL",
        owner,
        date(2000, 1, 1),
    )
    for category, pct, band in (("Ações Nacionais", 50, 5), ("Renda Fixa", 50, 5)):
        await conn.execute(
            "INSERT INTO portfolio_targets (user_id, category, target_pct, band_pp, valid_from) "
            "VALUES ($1::uuid, $2, $3, $4, $5)",
            owner,
            category,
            pct,
            band,
            month,
        )


@pytest.mark.asyncio
async def test_apply_allocation_excludes_goals_and_alerts(pool: Any, monkeypatch: Any) -> None:
    month = date(2097, 5, 1)
    classes = [
        _cls("acoes_br", [_asset("AAA3", "400", "a1"), _asset("BBB3", "200", "a2")]),
        _cls("renda_fixa", [_asset("CDB", "400")]),
        _cls(GOALS_BLOCK, [_asset("Nubank-SnowTrip", "1000", "g1")]),
    ]
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await _targets(conn, month)
            await allocation.apply_allocation(conn, classes, month)
            monkeypatch.setattr(allocation, "current_classes", _fixed(classes))
            ctx = AlertContext(today=date(2097, 5, 20), periodo=month, months=None, owner_id="x")  # type: ignore[arg-type]
            alerts = await allocation.allocation_alerts(conn, ctx)
        finally:
            await tx.rollback()
    acoes, rf, goals_block = classes
    assert (acoes.alocacao, acoes.meta, acoes.banda, acoes.desvio_pp) == (
        D("60.00"),
        D("50.00"),
        D("5.00"),
        D("10.00"),
    )  # base 1.000 sem os objetivos
    assert acoes.fora_banda and rf.fora_banda and goals_block.alocacao is None
    assert [a.alocacao for a in acoes.assets] == [D("66.67"), D("33.33")]  # dentro da classe
    assert acoes.assets[0].meta is None  # sem meta por ativo
    assert [a.message for a in alerts] == [
        "Ações Nacionais em 60,00%, meta 50,00% ± 5 p.p.",
        "Renda Fixa em 40,00%, meta 50,00% ± 5 p.p.",
    ]
    assert alerts[0].action is not None and alerts[0].action.label == "Ver aportes"


def _fixed(classes: list[PositionClass]) -> Any:
    async def current(conn: Any, owner: str, month: date) -> list[PositionClass]:
        return classes

    return current


@pytest.mark.asyncio
async def test_goal_assets_move_to_their_block(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    symbol = f"Nubank-Goal{uuid.uuid4().hex[:4]}"
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'Nubank', $2, 'Renda Fixa', "
            "'aporte', 300, 1, '2026-01-10')",
            owner,
            symbol,
        )
        asset = str(
            await conn.fetchval(
                "SELECT asset_id FROM asset_operations WHERE asset_symbol = $1", symbol
            )
        )
        goal = str(
            await conn.fetchval(
                "INSERT INTO goals (name, target, deadline) VALUES ('Teste 8.3', 1000, "
                "'2099-01-01') RETURNING id"
            )
        )
        await conn.execute(
            "INSERT INTO goal_assets (asset_id, goal_id, status) VALUES ($1::uuid, $2::uuid, "
            "'confirmed')",
            asset,
            goal,
        )
    try:
        r = await api.get(
            f"/api/v1/closing/positions?periodo={today_brt():%Y-%m}&leitura=mes",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        classes = {c["key"]: c for c in r.json()["classes"]}
        assert symbol in {a["symbol"] for a in classes[GOALS_BLOCK]["assets"]}
        assert symbol not in {a["symbol"] for a in classes["renda_fixa"]["assets"]}
        assert classes[GOALS_BLOCK]["alocacao"] is None  # fora da base da alocação
        assert "alocacao" in classes["renda_fixa"] and "desvio_pp" in classes["acoes_br"]
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM goal_assets WHERE asset_id = $1::uuid", asset)
            await conn.execute("DELETE FROM goals WHERE id = $1::uuid", goal)
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", symbol)
            await conn.execute("DELETE FROM asset_aliases WHERE asset_id = $1::uuid", asset)
            await conn.execute("DELETE FROM assets WHERE id = $1::uuid", asset)
