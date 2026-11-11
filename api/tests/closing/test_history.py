"""Story 9.1 — Histórico do fluxo: o período × o anterior × a média 12m; as razões vêm dos
componentes somados (nunca a média das razões); o anterior é a mesma leitura deslocada; "desde o
início" não compara; nunca entra mês depois do período."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engines.closing.history import Figures, _previous_months, _var
from engines.common.dates import today_brt

D = Decimal


def test_rate_from_summed_components() -> None:
    total = Figures()
    total.add(Figures(trabalho=D(1000), gastos=D(500), months=1))  # 50%
    total.add(Figures(trabalho=D(3000), gastos=D(2700), months=1))  # 10%
    assert total.taxa_poupanca == D(20)  # (4.000 − 3.200) ÷ 4.000, não (50 + 10) ÷ 2
    assert Figures().taxa_poupanca is None  # sem receita do trabalho


def test_previous_period() -> None:
    assert _previous_months(date(2026, 10, 1), "mes") == [date(2026, 9, 1)]
    assert _previous_months(date(2026, 11, 1), "tri") == [date(2026, 7, 1), date(2026, 8, 1)]
    prev_year = _previous_months(date(2026, 10, 1), "ano")
    assert prev_year is not None and (prev_year[0], prev_year[-1]) == (
        date(2025, 1, 1),
        date(2025, 10, 1),
    )
    assert _previous_months(date(2025, 3, 1), "ano") is None  # começaria antes de jul/2024
    assert _previous_months(date(2024, 7, 1), "mes") is None
    assert _previous_months(date(2026, 10, 1), "inicio") is None


def test_variation() -> None:
    assert _var("money", D(110), D(100)) == D("10.00")
    assert _var("money", D(100), D(100)) == D("0.00")  # zero = "0,00%" neutro
    assert _var("money", D(100), D(0)) is None
    assert _var("pct", D("23.5"), D("20.0")) == D("3.50")  # p.p.


@pytest.mark.asyncio
async def test_history_route(api, auth_headers) -> None:
    import main  # noqa: F401

    mes = f"{today_brt():%Y-%m}"
    r = await api.get(f"/api/v1/closing/history?periodo={mes}&leitura=mes", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [m["month"][:7] for m in body["months"]] == [mes]  # nunca mês depois do período
    assert {row["key"] for row in body["rows"]} >= {"receitas", "gastos", "taxa_poupanca"}
    assert body["previous_label"] is not None and body["average_months"] == 12
    # v2.2: a pizza dos gastos — um item por grupo com gasto, somando 100%
    share = body["groups_share"]
    assert all(s["value"] > 0 for s in share)
    assert not share or round(sum(s["pct"] for s in share), 2) == 100
    start = (
        await api.get(f"/api/v1/closing/history?periodo={mes}&leitura=inicio", headers=auth_headers)
    ).json()
    assert start["previous_label"] is None and start["average_months"] == 0
    assert all(r["previous"] is None and r["var_previous"] is None for r in start["rows"])
    future = await api.get("/api/v1/closing/history?periodo=2999-01", headers=auth_headers)
    assert future.status_code == 422


def test_planned_average_over_planned_months() -> None:
    """Revisão do Épico 9: a média do planejado é sobre os meses que tiveram plano."""
    window = Figures()
    for planned in (None, None, D(2200), D(2200)):
        window.add(
            Figures(planejado=planned, months=1, planned_months=1 if planned is not None else 0)
        )
    assert window.planned_months == 2 and window.planejado == D(4400)
    assert window.planejado / window.planned_months == D(2200)
