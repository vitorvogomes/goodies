"""Story 6.1 — casamento de custo fixo em `ledger/calc` (AD-7/AD-9): decisões de
`fixed_cost_payments` primeiro, depois o guloso global 1:1 (±10% do valor, −5/+5 dias do
vencimento) ordenado por (|Δvalor|, |Δdata|, fixed_cost_id, transaction_id); cada lado casa uma
vez. Custo que fica com outra candidata livre = "2 candidatas": nada pago até a escolha."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engines.ledger.calc import (
    CostDue,
    Decision,
    TxCandidate,
    due_date,
    match_fixed_costs,
)

D = Decimal


def _c(cid: str, amount: str, day: int) -> CostDue:
    return CostDue(cid, D(amount), date(2026, 10, day))


def _t(tid: str, amount: str, day: int) -> TxCandidate:
    return TxCandidate(tid, D(amount), date(2026, 10, day))


def test_due_date_clamps_to_month_end() -> None:
    assert due_date(date(2026, 2, 1), 31) == date(2026, 2, 28)
    assert due_date(date(2026, 10, 1), 5) == date(2026, 10, 5)


def test_tolerance_window() -> None:
    costs = [_c("a", "100.00", 10)]
    assert match_fixed_costs(costs, [_t("x", "110.00", 15)], [])["a"].transaction_id == "x"
    assert match_fixed_costs(costs, [_t("x", "110.01", 10)], [])["a"].status == "pendente"
    assert match_fixed_costs(costs, [_t("x", "100.00", 16)], [])["a"].status == "pendente"
    assert match_fixed_costs(costs, [_t("x", "100.00", 5)], [])["a"].status == "pago"
    assert match_fixed_costs(costs, [_t("x", "100.00", 4)], [])["a"].status == "pendente"


def test_greedy_global_order() -> None:
    # "b" casa com "y" (Δ 0) e "a" fica com "x", mesmo "x" sendo pior para "b"
    costs = [_c("a", "100.00", 10), _c("b", "105.00", 10)]
    txs = [_t("x", "100.00", 10), _t("y", "105.00", 10)]
    m = match_fixed_costs(costs, txs, [])
    assert (m["a"].transaction_id, m["b"].transaction_id) == ("x", "y")


def test_tie_breaks_by_ids() -> None:
    # dois custos iguais, duas transações iguais: cada lado casa uma vez, pela ordem dos ids
    costs = [_c("b", "50.00", 10), _c("a", "50.00", 10)]
    txs = [_t("y", "50.00", 10), _t("x", "50.00", 10)]
    m = match_fixed_costs(costs, txs, [])
    assert (m["a"].transaction_id, m["b"].transaction_id) == ("x", "y")
    assert m["a"].status == m["b"].status == "pago"


def test_two_candidates_nothing_paid() -> None:
    m = match_fixed_costs([_c("a", "80.00", 10)], [_t("x", "80.00", 9), _t("y", "81.00", 12)], [])
    assert m["a"].status == "pendente" and m["a"].transaction_id is None
    assert m["a"].candidates == ["x", "y"]


def test_decisions_first() -> None:
    costs = [_c("a", "100.00", 10), _c("b", "100.00", 10), _c("c", "30.00", 20)]
    txs = [_t("x", "100.00", 10), _t("y", "100.00", 11)]
    decisions = [
        Decision("a", "corrigido", "y"),  # escolha do Vitor, fora da ordem do guloso
        Decision("c", "manual", None),
    ]
    m = match_fixed_costs(costs, txs, decisions)
    assert (m["a"].transaction_id, m["a"].source) == ("y", "decisao")
    assert (m["b"].transaction_id, m["b"].source) == ("x", "auto")
    assert (m["c"].status, m["c"].transaction_id) == ("manual", None)


def test_undone_blocks_auto_match() -> None:
    m = match_fixed_costs(
        [_c("a", "100.00", 10)], [_t("x", "100.00", 10)], [Decision("a", "desfeito", "x")]
    )
    assert m["a"].status == "pendente" and m["a"].candidates == []
