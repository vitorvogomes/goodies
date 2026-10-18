"""Story 2.5 — regra vencedora: direção pelo sinal, mais longa, empate → mais recente."""

from datetime import UTC, datetime
from decimal import Decimal

from engines.ledger.calc import Rule, best_rule

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 6, 1, tzinfo=UTC)


def _r(pattern: str, direction: str, cat: str, when: datetime = T0) -> Rule:
    return Rule(
        pattern, direction, cat, cat, "expense", rule_id=f"{pattern}-{direction}", created_at=when
    )


RULES = [
    _r("rdb", "saida", "invest"),
    _r("rdb", "entrada", "resgate"),
    _r("aplicação rdb", "saida", "invest-longa"),
    _r("uber", "ambos", "transporte"),
]


def test_direction_by_sign() -> None:
    assert best_rule("Resgate RDB", Decimal("10"), RULES).category_id == "resgate"
    assert best_rule("RDB qualquer", Decimal("-10"), RULES).category_id == "invest"


def test_longest_pattern_wins() -> None:
    assert best_rule("Aplicação RDB - Caixinha", Decimal("-5"), RULES).category_id == "invest-longa"


def test_tie_goes_to_most_recent() -> None:
    rules = [_r("ifood", "saida", "antiga", T0), _r("ifood", "saida", "nova", T1)]
    assert best_rule("IFOOD *pedido", Decimal("-30"), rules).category_id == "nova"


def test_both_directions_and_no_match() -> None:
    assert best_rule("UBER *TRIP", Decimal("-20"), RULES).category_id == "transporte"
    assert best_rule("UBER estorno", Decimal("20"), RULES).category_id == "transporte"
    assert best_rule("Padaria", Decimal("-3"), RULES) is None
    assert best_rule("", Decimal("-3"), RULES) is None


# --- termos de dinheiro (Story 2.6) ---
from engines.ledger.calc import (  # noqa: E402
    Movement,
    devolucoes,
    gastos,
    month_result,
    resgates,
    savings_rate,
    work_income,
)


def _m(amount: str, kind: str, role: str) -> Movement:
    return Movement(Decimal(amount), kind, role)


MES = [
    _m("8781.08", "income", "work_income"),
    _m("3000", "income", "work_income"),
    _m("500", "income", "resgate"),
    _m("100", "income", "devolucao"),
    _m("164.12", "income", "a_classificar"),
    _m("-4000", "expense", "consumo"),
    _m("-60.92", "expense", "a_classificar"),
    _m("20", "expense", "consumo"),  # estorno em gasto: segue bruto, abate
    _m("-1000", "investment", "investimento"),
    _m("0", "transfer", "transferencia"),
]


def test_terms_by_role_never_by_name() -> None:
    assert work_income(MES) == Decimal("11781.08")
    assert resgates(MES) == Decimal("500")
    assert devolucoes(MES) == Decimal("100")
    assert gastos(MES) == Decimal("4040.92")


def test_savings_rate_formula() -> None:
    # (11781.08 - (4040.92 - 100)) / 11781.08
    expected = (Decimal("11781.08") - (Decimal("4040.92") - Decimal("100"))) / Decimal("11781.08")
    assert savings_rate(MES) == expected


def test_savings_rate_without_work_income_is_none_not_zero() -> None:
    assert savings_rate([_m("500", "income", "resgate"), _m("-10", "expense", "consumo")]) is None


def test_month_result() -> None:
    # receitas 12545.20 - gastos 4040.92 - investimento 1000
    assert month_result(MES) == Decimal("7504.28")
