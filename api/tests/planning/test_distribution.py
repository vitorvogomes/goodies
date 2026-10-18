"""Story 8.5 — distribuição do aporte (AD-12), golden tests da função pura: ordem fixa (reserva →
objetivos → classes → ativos), soma ao centavo, pisos reduzidos em proporção, acima da banda só o
piso, monotônica no déficit, nunca venda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engines.planning.distribution import (
    AssetState,
    ClassLine,
    ClassState,
    Distribution,
    GoalNeed,
    distribute,
    round_cents,
)

D = Decimal


def _classes() -> list[ClassState]:
    # base 10.000: ações 2.140 (meta 25 ± 3), ETFs 1.410 (15), FIIs 1.320 (15), RF 2.280 (20),
    # aposentadoria 1.690 (15), cripto 1.160 (10)
    return [
        ClassState(
            "acoes_br",
            "Ações Nacionais",
            D(2140),
            D(25),
            D(3),
            D(0),
            (
                AssetState("bbas3", "BBAS3", D(540), D(30)),
                AssetState("itsa4", "ITSA4", D(500), D(25)),
                AssetState("egie3", "EGIE3", D(580), D(25)),
                AssetState("taee11", "TAEE11", D(520), D(20)),
            ),
        ),
        ClassState("etfs", "ETFs", D(1410), D(15), D(3), D(0)),
        ClassState("fiis", "FIIs", D(1320), D(15), D(3), D(0)),
        ClassState("renda_fixa", "Renda Fixa", D(2280), D(20), D(3), D(200)),
        ClassState("aposentadoria", "Aposentadoria", D(1690), D(15), D(3), D(300)),
        ClassState("cripto", "Cripto", D(1160), D(10), D(3), D(100)),
    ]


GOALS = [
    GoalNeed("res", "Reserva de emergência", "reserva", D("20474.40"), D(18900), 4),
    GoalNeed("snow", "Snow Trip", "objetivo", D(15000), D(6250), 10, date(2027, 7, 31)),
]


def _by(dist: Distribution) -> tuple[dict[str, Decimal], dict[str, ClassLine]]:
    return {g.id: g.sugerido for g in dist.goals}, {c.cls: c for c in dist.classes}


def test_order_and_cents() -> None:
    d = distribute(D(4500), GOALS, _classes())
    goals, classes = _by(d)
    assert goals == {"res": D("393.60"), "snow": D("875.00")}  # 1.574,40 ÷ 4 · 8.750 ÷ 10
    total = sum(goals.values()) + sum(c.sugerido for c in classes.values())
    assert total == D("4500.00") and not d.floors_reduced and d.has_targets
    assert all(c.sugerido >= c.floor for c in classes.values())  # nunca abaixo do piso
    assert all(c.sugerido >= 0 for c in classes.values())  # nunca venda


def test_above_band_gets_only_floor_and_monotonic() -> None:
    classes = _classes()
    classes[3] = ClassState("renda_fixa", "Renda Fixa", D(4000), D(20), D(3), D(200))  # 34% > 23%
    _, by = _by(distribute(D(3000), [], classes))
    assert by["renda_fixa"].floor_only and by["renda_fixa"].sugerido == D("200.00")
    assert by["renda_fixa"].out_of_band and not by["etfs"].out_of_band  # ETFs: −2,97 p.p.
    # maior déficit → maior sugestão (ações abaixo da meta mais que ETFs)
    assert by["acoes_br"].sugerido > by["etfs"].sugerido > D(0)


def test_floors_above_available_are_reduced() -> None:
    d = distribute(D(400), [], _classes())  # pisos somam 600
    _, by = _by(d)
    assert d.floors_reduced
    assert (by["renda_fixa"].sugerido, by["aposentadoria"].sugerido, by["cripto"].sugerido) == (
        D("133.33"),
        D("200.00"),
        D("66.67"),
    )
    assert sum(c.sugerido for c in by.values()) == D("400.00")


def test_reserve_never_overfills_and_goals_share_when_short() -> None:
    almost = [GoalNeed("res", "Reserva", "reserva", D(1000), D(950), 12)]
    assert _by(distribute(D(100), almost, []))[0]["res"] == D("4.17")  # 50 ÷ 12
    full = [GoalNeed("res", "Reserva", "reserva", D(1000), D(1200), 12)]
    assert _by(distribute(D(100), full, []))[0]["res"] == D("0.00")
    short = [
        GoalNeed("a", "A", "objetivo", D(3000), D(0), 1),
        GoalNeed("b", "B", "objetivo", D(1000), D(0), 1),
    ]
    assert _by(distribute(D(400), short, []))[0] == {"a": D("300.00"), "b": D("100.00")}


def test_assets_by_deficit_inside_class() -> None:
    _, by = _by(distribute(D(4500), GOALS, _classes()))
    acoes = by["acoes_br"]
    amounts = {a.id: a.sugerido for a in acoes.assets}
    assert sum(amounts.values()) == acoes.sugerido
    assert amounts["bbas3"] > amounts["taee11"]  # BBAS3 é o mais abaixo da meta (25,2% × 30%)
    no_targets = by["etfs"].assets
    assert no_targets == []


def test_without_targets_has_no_class_base() -> None:
    flat = [ClassState(c.cls, c.label, c.value, D(0), D(3), D(0)) for c in _classes()]
    d = distribute(D(1000), GOALS, flat)
    assert not d.has_targets
    assert d.unassigned == D(1000) - sum(g.sugerido for g in d.goals)


def test_locks_are_fixed_and_rest_redistributes() -> None:
    d = distribute(D(4500), GOALS, _classes(), {"class:fiis": D(800)})
    _, by = _by(d)
    assert by["fiis"].sugerido == D("800.00") and by["fiis"].locked
    assert sum(g.sugerido for g in d.goals) + sum(c.sugerido for c in by.values()) == D("4500.00")
    assert d.locks_total == D(800)


def test_round_cents_closes() -> None:
    parts = round_cents({"a": D(1) / 3, "b": D(1) / 3, "c": D(1) / 3}, D("1.00"))
    assert sum(parts.values()) == D("1.00") and sorted(parts.values()) == [
        D("0.33"),
        D("0.33"),
        D("0.34"),
    ]


@pytest.mark.asyncio
async def test_preview_route(api, auth_headers) -> None:
    import main  # noqa: F401

    url = "/api/v1/planning/distribution/preview"
    r = await api.post(url, json={"mes": "2093-04"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["aporte_definido"] is False  # mês sem plano
    r = await api.post(url, json={"mes": "2093-04", "planejado": "3000.00"}, headers=auth_headers)
    body = r.json()
    assert body["aporte_definido"] is True and body["planned"] == 3000.0
    assert body["goals"][0]["kind"] == "reserva"
    placed = sum(D(str(g["sugerido"])) for g in body["goals"]) + sum(
        D(str(c["sugerido"])) for c in body["classes"]
    )
    assert placed + D(str(body["unassigned"])) == D("3000.00")
    assert all(c["sugerido"] >= c["floor"] or body["floors_reduced"] for c in body["classes"])
    bad = await api.post(url, json={"mes": "2093-4"}, headers=auth_headers)
    assert bad.status_code == 422
