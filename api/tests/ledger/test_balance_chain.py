"""Story 3.12 — conferência encadeada da conta PF: saldo de abertura pela âncora, cada intervalo
entre saldos informados confere ao centavo e a diferença fica isolada nele; mês conferido = primeiro
saldo com data ≥ fim do mês com tudo batendo até ele."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from engines.ledger.calc import chained_check, month_checked, opening_balance

TX = [
    (date(2024, 7, 10), D("100.00")),
    (date(2024, 7, 31), D("-30.00")),
    (date(2024, 8, 5), D("-20.00")),
    (date(2024, 8, 31), D("50.00")),
    (date(2024, 9, 15), D("-10.00")),
]


def test_opening_balance_from_anchor() -> None:
    # saldo informado em 31/07 = 570 → abertura = 570 − (100 − 30) = 500
    assert opening_balance(D("570.00"), date(2024, 7, 31), TX) == D("500.00")


def test_chain_isolates_the_divergent_interval() -> None:
    reported = [
        (date(2024, 7, 31), D("570.00")),
        (date(2024, 8, 31), D("600.00")),  # 570 − 20 + 50 = 600 ✓
        (date(2024, 9, 30), D("585.00")),  # esperado 590 → diferença −5
        (date(2024, 10, 31), D("585.00")),  # nada no intervalo: confere com o anterior informado
    ]
    intervals = chained_check(reported, TX)
    assert [(i.end, i.difference, i.ok) for i in intervals] == [
        (date(2024, 8, 31), D("0.00"), True),
        (date(2024, 9, 30), D("-5.00"), False),
        (date(2024, 10, 31), D("0.00"), True),
    ]
    assert intervals[1].start == date(2024, 8, 31)
    assert intervals[1].expected == D("590.00")


def test_month_checked_uses_first_balance_after_month_end() -> None:
    reported = [
        (date(2024, 7, 31), D("570.00")),
        (date(2024, 8, 3), D("550.00")),  # semanal: 570 − 20 (05/08 ainda não) = … não bate
        (date(2024, 9, 2), D("600.00")),
    ]
    tx = [(date(2024, 8, 2), D("-20.00")), (date(2024, 8, 31), D("50.00"))]
    intervals = chained_check(reported, tx)
    assert [i.ok for i in intervals] == [True, True]
    assert month_checked(intervals, date(2024, 8, 31)) is True  # 02/09 é o 1º ≥ 31/08
    assert month_checked(intervals, date(2024, 9, 30)) is False  # nenhum saldo depois
    broken = chained_check([(date(2024, 7, 31), D("570")), (date(2024, 8, 3), D("1"))], tx)
    assert month_checked(broken + intervals[1:], date(2024, 8, 31)) is False
