"""v2.2 — fluxo do mês do Painel: para onde foram as entradas (trabalho + resgates). Os mesmos
termos do orçamento (o número da frase é o `restante`), em fatias de uma barra que somam 100%."""

from __future__ import annotations

from decimal import Decimal

from engines.planning.calc import BudgetInput, budget, month_flow

D = Decimal


def _b(trabalho: str, consumido: str, *, resgates: str = "0") -> object:
    return budget(
        BudgetInput(
            trabalho=D(trabalho),
            resgates=D(resgates),
            custos_fixos=D("4000"),
            aporte_planejado=D("3500"),
            dividas_informadas=D("500"),
            dividas_prefill=D(0),
            consumido=D(consumido),
        )
    )


def test_surplus_splits_income_and_ends_with_what_is_left() -> None:
    flow = month_flow(_b("10000", "1000"))
    assert flow.entradas == D("10000") and flow.sobra == D("1000")
    assert [(p.key, p.value, p.pct) for p in flow.parts] == [
        ("custos_fixos", D("4000"), D("40.00")),
        ("aporte", D("3500"), D("35.00")),
        ("dividas", D("500"), D("5.00")),
        ("gastos", D("1000"), D("10.00")),
        ("sobra", D("1000"), D("10.00")),
    ]
    assert flow.limite_pct == D("100.00")


def test_shortfall_scales_to_what_went_out_and_marks_where_income_ends() -> None:
    # entradas 8.000 + resgate 500; saídas 4.000 + 3.500 + 500 + 1.180 = 9.180 → faltam 680
    flow = month_flow(_b("8000", "1180", resgates="500"))
    assert flow.entradas == D("8500") and flow.sobra == D("-680")
    assert [p.key for p in flow.parts] == ["custos_fixos", "aporte", "dividas", "gastos"]
    assert sum(p.pct for p in flow.parts) == D("100.00")
    assert flow.limite_pct == D("92.59")  # 8.500 ÷ 9.180


def test_zero_parts_are_left_out_and_empty_month_has_no_bar() -> None:
    empty = month_flow(budget(BudgetInput(D(0), D(0), D(0), None, None, D(0), D(0))))
    assert empty.parts == [] and empty.limite_pct is None


def test_rounded_pcts_always_sum_100() -> None:
    flow = month_flow(_b("9000.03", "333.33"))
    assert sum(p.pct for p in flow.parts) == D("100.00")


def test_refunds_above_spending_with_surplus_keep_income_line_at_100() -> None:
    """Review v2.2: devoluções acima dos gastos (consumido < 0) e sobra positiva — o termo
    negativo sai da barra e o traço das entradas fica no fim (nada de "passou" com sobra)."""
    flow = month_flow(_b("10000", "-200"))
    assert flow.sobra > 0 and flow.limite_pct == D("100.00")
    assert "gastos" not in [p.key for p in flow.parts]
