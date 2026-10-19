"""Distribuição por lote (pedido de 18/10/2026): o sugerido de cada ativo é o que se compra de
fato — cotas inteiras na B3, frações de 0,01 título no Tesouro com a ordem mínima de R$ 30 — e o
troco das cotas vai para uma classe de valor livre (Renda Fixa), sem sugerir R$ 11,81 de um FII de
R$ 105,99.
"""

from __future__ import annotations

from decimal import Decimal

from engines.planning.distribution import (
    AssetState,
    ClassState,
    Distribution,
    Lot,
    buy_units,
    distribute,
    tesouro_lot,
    units,
)

D = Decimal


def _fiis() -> ClassState:
    # abaixo da meta; dentro dela, XPML11 tem o maior déficit e a cota custa R$ 105,99
    return ClassState(
        "fiis",
        "FIIs",
        D(500),
        D(10),
        D(5),
        D(0),
        (
            AssetState("kncr", "KNCR11", D(300), D(50), Lot(D("105.66"))),
            AssetState("xpml", "XPML11", D(200), D(50), Lot(D("105.99"))),
        ),
    )


def _rf(value: Decimal = Decimal(8000)) -> ClassState:
    return ClassState(
        "renda_fixa",
        "Renda Fixa",
        value,
        D(90),
        D(10),
        D(0),
        (AssetState("flash", "Flash", value, None),),
    )


def _by(d: Distribution) -> dict[str, object]:
    return {c.cls: c for c in d.classes}


def test_never_suggests_a_fraction_of_a_share() -> None:
    # os R$ 40 vão todos aos FIIs (a RF está acima da meta) e nenhum ativo pede ½ cota
    d = distribute(D("40.00"), [], [_fiis(), _rf()])
    fiis, rf = _by(d)["fiis"], _by(d)["renda_fixa"]
    assert {a.id: a.cotas for a in fiis.assets} == {"kncr": D(0), "xpml": D(0)}
    assert fiis.sugerido == D(0) and fiis.troco == D("40.00")
    # o que não compra cota inteira vai para a classe de valor livre; o total fecha no planejado
    assert rf.recebido_troco == D("40.00") and rf.sugerido == D("40.00")
    assert d.troco == D("40.00") and d.troco_destino == ["Renda Fixa"]


def test_each_b3_suggestion_is_whole_shares() -> None:
    d = distribute(D("130.00"), [], [_fiis(), _rf()])
    fiis = _by(d)["fiis"]
    for a in fiis.assets:
        assert a.cotas is not None and a.cotas == a.cotas.to_integral_value()
        assert a.sugerido == (a.cotas * D(str(a.preco))).quantize(D("0.01"))
    assert fiis.sugerido == sum(a.sugerido for a in fiis.assets) == D("105.99")
    assert sum(c.sugerido for c in d.classes) == D("130.00")


def test_rounds_to_the_nearest_whole_share() -> None:
    # XPML11 pede R$ 150 (1,4 cota): compra 1; KNCR11 pede R$ 50 (0,47 cota): nenhuma
    d = distribute(D("200.00"), [], [_fiis(), _rf()])
    fiis = _by(d)["fiis"]
    assert {a.id: a.cotas for a in fiis.assets} == {"kncr": D(0), "xpml": D(1)}
    assert fiis.sugerido == D("105.99")


def test_tesouro_minimum_order_and_hundredth_of_a_title() -> None:
    lot = tesouro_lot(D("3233.78"))
    assert (lot.qty, lot.minimum) == (D("0.01"), D(30))
    small = tesouro_lot(D("1062.80"))  # 0,01 título = R$ 10,63 → a ordem mínima pede 3
    assert small.first_increments == 3
    cls = ClassState(
        "aposentadoria",
        "Aposentadoria",
        D(500),
        D(10),
        D(3),
        D(0),
        (
            AssetState("ipca32", "Tesouro IPCA+ 2032", D(100), D(60), lot),
            AssetState("pre32", "Tesouro Prefixado 2032", D(400), D(40), small),
        ),
    )
    d = distribute(D("700.00"), [], [cls, _rf(D(5000))])
    apos = _by(d)["aposentadoria"]
    assert apos.sugerido > 0
    for a in apos.assets:
        if a.cotas:
            assert a.sugerido >= D(30)  # nunca abaixo da ordem mínima
            assert (a.cotas / D("0.01")) == (a.cotas / D("0.01")).to_integral_value()


def test_without_a_free_class_the_change_stays_unassigned() -> None:
    d = distribute(D("50.00"), [], [_fiis()])
    fiis = _by(d)["fiis"]
    assert fiis.sugerido == D(0) and d.troco_destino == []
    assert d.unassigned == D("50.00")


def test_free_assets_keep_exact_cents() -> None:
    # sem preço (renda fixa, cripto), o sugerido segue ao centavo, como antes
    d = distribute(D("1000.00"), [], [_rf()])
    rf = _by(d)["renda_fixa"]
    assert rf.sugerido == D("1000.00") and rf.troco == D(0) and d.troco == D(0)


def test_buy_list_is_the_plan_left_within_the_class_pending() -> None:
    # ETFs de out/2026: o plano pedia 15 NASD11 e 11 ACWI11 (R$ 494,91), mas GOLD11 e ALUG11
    # entraram fora do plano e só faltam R$ 351,49 na classe → a lista cabe nisso, inteira
    wanted = {
        "nasd": (Lot(D("20.63")), D(15) * D("20.63")),
        "acwi": (Lot(D("16.86")), D(11) * D("16.86")),
    }
    n = buy_units(wanted, D("351.49"))
    assert n == {"nasd": 10, "acwi": 8}
    assert sum(wanted[k][0].cost(v) for k, v in n.items()) <= D("351.49")
    # cabendo tudo, o que falta do plano vem inteiro
    assert buy_units(wanted, D(1000)) == {"nasd": 15, "acwi": 11}
    assert buy_units(wanted, D(0)) == {"nasd": 0, "acwi": 0}


def test_lot_by_asset_kind() -> None:
    from engines.planning.distribution_service import lot_for

    assert lot_for("b3:XPML11", D("105.99")) == Lot(D("105.99"))
    assert lot_for("td:Tesouro IPCA+ 2032", D("3233.78")) == tesouro_lot(D("3233.78"))
    assert lot_for("debenture:flash", D(1)) is None  # valor livre
    assert lot_for("crypto:BTC", D(400000)) is None
    assert lot_for("b3:X", None) is None  # sem preço, sem lote
    assert units(tesouro_lot(D("3233.78")), 3) == D("0.03")
    assert units(Lot(D(10)), 10) == D(10)


def test_fixed_asset_in_a_class_without_asset_targets() -> None:
    # a Flash fixa em R$ 1.000: a classe recebe só isso (sem meta por ativo) e o resto vai às outras
    rf = ClassState(
        "renda_fixa",
        "Renda Fixa",
        D(8000),
        D(45),
        D(10),
        D(0),
        (AssetState("flash", "Flash", D(7800), None), AssetState("cdb", "CDB", D(200), None)),
    )
    d = distribute(
        D(3000), [], [rf, _fiis()], {"asset:flash": D(1000), "class:renda_fixa": D(1000)}
    )
    line = _by(d)["renda_fixa"]
    assert line.sugerido == D("1000.00") and line.locked
    assert {a.id: a.sugerido for a in line.assets} == {"flash": D("1000.00"), "cdb": None}
    # sem classe livre para o troco das cotas dos FIIs: fica sem destino, e o total fecha
    fiis = _by(d)["fiis"]
    assert fiis.sugerido + line.sugerido + d.unassigned == D(3000)


def test_change_goes_reserve_then_turbo_then_closest_goal() -> None:
    """Pedido de 18/10/2026: o troco das cotas vai à reserva até encher, à caixinha Turbo até o teto
    dela e ao objetivo mais perto de ser concluído; objetivo travado (aporte fixo) não recebe."""
    from engines.planning.distribution import GoalNeed, TrocoSink

    fiis = _fiis()  # R$ 40 em FIIs não compram cota inteira: tudo vira troco
    reserve = GoalNeed("res", "Reserva", "reserva", D(1000), D(990), 12)  # falta R$ 10
    trip = GoalNeed("trip", "Viagem", "objetivo", D(1000), D(900), 10)
    sinks = [
        TrocoSink("res", "Reserva"),
        TrocoSink("res", "Caixinha Turbo", D(15)),
        TrocoSink("trip", "Viagem"),
    ]
    d = distribute(D("41.67"), [reserve, trip], [fiis], {"goal:trip": D(0)}, sinks)
    goals = {g.id: g for g in d.goals}
    # reserva: o mensal (10 ÷ 12 = 0,83) + o resto até encher; Turbo: R$ 15; a viagem travada não
    assert goals["res"].recebido_troco == D("24.17") and goals["res"].sugerido == D("25.00")
    assert goals["trip"].sugerido == D(0) and goals["trip"].recebido_troco == D(0)
    assert d.troco_destino == ["Reserva", "Caixinha Turbo"] and d.troco == D("24.17")
    assert d.unassigned == D("16.67")  # sem classe livre: o resto fica sem destino
    # destravada, a viagem leva o que sobrou
    d = distribute(D("41.67"), [reserve, trip], [fiis], {}, sinks)
    goals = {g.id: g for g in d.goals}
    assert d.troco_destino[-1] == "Viagem" and d.unassigned == D(0)
    total = sum(g.sugerido for g in d.goals) + sum(c.sugerido for c in d.classes)
    assert total == D("41.67")


def test_troco_sinks_order() -> None:
    """Na posição do início do mês: reserva, a Turbo dela até R$ 5 mil, e os objetivos do mais perto
    de ser concluído ao mais longe (o concluído não entra)."""
    from engines.planning.distribution import GoalNeed
    from engines.planning.distribution_service import troco_sinks

    needs = [
        GoalNeed("res", "Reserva", "reserva", D(25000), D(9000), 12),
        GoalNeed("a", "A", "objetivo", D(20000), D(14000), 9),
        GoalNeed("b", "B", "objetivo", D(50000), D(4000), 12),
        GoalNeed("done", "Done", "objetivo", D(100), D(100), 1),
    ]
    sinks = troco_sinks(needs, ("res", "Caixinha Turbo", D(1200)))
    assert [(s.goal_id, s.label, s.capacity) for s in sinks] == [
        ("res", "Reserva", None),
        ("res", "Caixinha Turbo", D(3800)),
        ("a", "A", None),  # 70% do alvo
        ("b", "B", None),  # 8%: o próximo, se o primeiro estiver travado
    ]
    assert troco_sinks(needs, ("outro", "Caixinha Turbo", D(0)))[1].goal_id == "a"


def test_buy_list_keeps_locked_and_free_assets_of_a_lotted_class() -> None:
    """Review: na classe com cotas, o ativo travado/fixo (sem cotas do plano) e o ativo de valor
    livre entram na lista — antes viravam "troco que não compra cota inteira"."""
    from engines.planning.distribution import AssetLine, ClassLine
    from engines.planning.distribution_service import buy_list

    def asset(aid: str, sug: str, cotas: str | None = None, locked: bool = False) -> AssetLine:
        return AssetLine(aid, aid, D(10), D(10), D(sug), locked, cotas=D(cotas) if cotas else None)

    cl = ClassLine(
        "acoes_br",
        "Ações",
        D(10),
        D(10),
        D(0),
        D(3),
        D(0),
        D(500),
        False,
        assets=[asset("petr", "119.36", "2"), asset("itsa", "100", locked=True), asset("rf", "50")],
    )
    lots = {"petr": Lot(D("59.68")), "itsa": Lot(D("15.43"))}
    n, free, total, troco = buy_list(cl, D(500), lots, {}, {})
    assert n == {"petr": 2, "itsa": 6}  # ITSA4 fixo em R$ 100 → 6 cotas inteiras (R$ 92,58)
    assert free == {"rf": D(50)}
    assert total == D("119.36") + D("92.58") + D(50) and troco == D(500) - total
    # o que já entrou no mês sai da lista (cotas no plano; R$ no travado e no livre)
    n, free, *_ = buy_list(cl, D(200), lots, {"petr": D(2)}, {"itsa": D(100), "rf": D(20)})
    assert n == {"petr": 0, "itsa": 0} and free == {"rf": D(30)}
