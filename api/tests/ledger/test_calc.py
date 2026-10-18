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
