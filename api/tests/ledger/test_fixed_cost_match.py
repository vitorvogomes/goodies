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


# ---- P13: a palavra do custo primeiro (a partir de nov/2026) ----


def _cn(cid: str, name: str, amount: str, day: int) -> CostDue:
    return CostDue(cid, D(amount), date(2026, 11, day), name)


def _tn(tid: str, description: str, amount: str, day: int) -> TxCandidate:
    return TxCandidate(tid, D(amount), date(2026, 11, day), description)


def test_name_beats_closer_amount() -> None:
    """A transação com a palavra do custo casa, mesmo com o valor mais longe que outra."""
    m = match_fixed_costs(
        [_cn("a", "Academia Smart Fit", "120.00", 10)],
        [
            _tn("x", "Pix enviado - Mercado Bom Preço", "120.00", 10),
            _tn("y", "SMARTFIT BRASIL", "129.90", 18),
        ],
        [],
    )
    assert (m["a"].status, m["a"].transaction_id) == ("pago", "y")


def test_name_match_ignores_accents_and_generic_words() -> None:
    m = match_fixed_costs(
        [_cn("a", "Condomínio do prédio", "1500.00", 5)],
        [_tn("x", "Pagamento de boleto - CONDOMINIO EDIF", "1530.00", 7)],
        [],
    )
    assert m["a"].transaction_id == "x"
    generic = match_fixed_costs(
        [_cn("b", "Pagamento de boleto", "50.00", 5)],
        [_tn("y", "Pagamento de boleto - LOJA", "50.00", 5)],
        [],
    )  # só palavra genérica em comum: não é casamento pelo nome
    assert generic["b"].status == "pendente" and generic["b"].candidates == ["y"]


def test_amount_only_is_never_paid_automatically() -> None:
    """Sem a palavra do custo, o valor aproximado só sugere: fica pendente com a candidata."""
    m = match_fixed_costs(
        [_cn("a", "Internet", "100.00", 10)], [_tn("x", "Restaurante", "100.00", 10)], []
    )
    assert m["a"].status == "pendente" and m["a"].candidates == ["x"]


def test_months_before_cutoff_keep_the_amount_rule() -> None:
    """Os meses até out/2026 já foram conferidos: seguem a regra do valor (nada muda neles)."""
    m = match_fixed_costs([_c("a", "100.00", 10)], [_t("x", "100.00", 10)], [])
    assert m["a"].status == "pago"


def test_undone_cost_gets_no_automatic_replacement() -> None:
    """P13 (mai/2025): desfeito o casamento, o custo não ganha outro automático pelo valor — a
    próxima saída de valor parecido fica só como candidata."""
    m = match_fixed_costs(
        [_c("a", "100.00", 10)],
        [_t("x", "100.00", 10), _t("y", "101.00", 11)],
        [Decision("a", "desfeito", "x")],
    )
    assert m["a"].status == "pendente" and m["a"].candidates == ["y"]


def test_every_undone_transaction_stays_out() -> None:
    m = match_fixed_costs(
        [_c("a", "100.00", 10)],
        [_t("x", "100.00", 10), _t("y", "101.00", 11)],
        [Decision("a", "desfeito", "x"), Decision("a", "desfeito", "y")],
    )
    assert m["a"].status == "pendente" and m["a"].candidates == []


# ---- Receitas esperadas (Ajustes › Custos e receitas, pedido de 18/10/2026) ----


def test_expected_income_by_payer_and_name() -> None:
    from engines.ledger.calc import ExpectedIncome, IncomeTx, match_expected_incomes

    expected = [
        ExpectedIncome("a", "Salário", D("5000"), date(2026, 10, 5), "Flash"),
        ExpectedIncome("b", "Aluguel sala", D("800"), date(2026, 10, 10), None),
        ExpectedIncome("c", "Freela", D("1200"), date(2026, 10, 25), "Cliente X"),
    ]
    incomes = [
        IncomeTx("t1", D("3000"), date(2026, 10, 5), "Pix recebido", "FLASH"),
        IncomeTx("t2", D("2000"), date(2026, 10, 6), "Pix recebido", "Flash"),
        IncomeTx("t3", D("800"), date(2026, 10, 11), "Aluguel da sala", None),
        IncomeTx("t4", D("99"), date(2026, 10, 12), "Outro", None),
    ]
    m = {x.income_id: x for x in match_expected_incomes(expected, incomes, date(2026, 10, 20))}
    assert (m["a"].received, m["a"].status) == (D("5000"), "recebido")
    assert (m["b"].received, m["b"].status) == (D("800"), "recebido")
    assert (m["c"].received, m["c"].status, m["c"].pending) == (D(0), "a_receber", D("1200"))
    late = match_expected_incomes(expected[2:], [], date(2026, 10, 26))[0]
    assert late.status == "atrasado"
