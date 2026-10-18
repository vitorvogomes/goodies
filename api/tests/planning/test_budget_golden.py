"""Story 6.5 — golden do orçamento a partir de `tests/fixtures/mockup_out2026.json` (os insumos do
mockup de Caixa › Orçamento): consumido R$ 6.912,37, disponível R$ 8.405,59, financiado R$ 2.994,77;
casos zero, resgate cobre tudo, com devolução, e dívida paga com o campo não informado."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from engines.ledger.calc import (
    CostDue,
    Movement,
    SpendTx,
    TxCandidate,
    consumido,
    due_date,
    match_fixed_costs,
    work_income,
)
from engines.ledger.calc import resgates as calc_resgates
from engines.planning.calc import (
    BudgetInput,
    budget,
    consumo_financiado,
    custos_fixos_do_mes,
)

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "mockup_out2026.json").read_text(encoding="utf-8")
)
D = Decimal
MONTH = date(2026, 10, 1)


def _inputs(fx: dict) -> BudgetInput:
    txs = fx["transactions"]
    moves = [Movement(D(t["amount"]), t["kind"], t["role"]) for t in txs]
    costs = [
        CostDue(c["id"], D(c["amount"]), due_date(MONTH, c["due_day"])) for c in fx["fixed_costs"]
    ]
    candidates = [
        TxCandidate(t["id"], -D(t["amount"]), date.fromisoformat(t["date"]))
        for t in txs
        if t["kind"] == "expense"
    ]
    matches = match_fixed_costs(costs, candidates, [])
    paid_by_tx = {t["id"]: -D(t["amount"]) for t in txs}
    spend = [SpendTx(t["id"], D(t["amount"]), t["kind"], t["role"]) for t in txs]
    matched = {m.transaction_id for m in matches.values() if m.transaction_id}
    cons = consumido(spend, matched)
    return BudgetInput(
        trabalho=work_income(moves),
        resgates=calc_resgates(moves),
        custos_fixos=custos_fixos_do_mes(
            [(c.amount, paid_by_tx.get(matches[c.cost_id].transaction_id or "")) for c in costs]
        ),
        aporte_planejado=D(fx["plan"]["aporte_planejado"])
        if fx["plan"]["aporte_planejado"]
        else None,
        dividas_informadas=D(fx["plan"]["dividas"]) if fx["plan"]["dividas"] is not None else None,
        dividas_prefill=cons.dividas,
        consumido=cons.total,
    )


def test_mockup_golden() -> None:
    exp = FIXTURE["expected"]
    b = budget(_inputs(FIXTURE))
    assert b.disponivel == D(exp["disponivel"])
    assert b.consumido == D(exp["consumido"])
    assert b.restante == D(exp["restante"])
    assert b.consumo_financiado == D(exp["consumo_financiado"])
    assert b.restante_sem_resgates == D(exp["restante_sem_resgates"])
    assert b.custos_fixos == D(exp["custos_fixos"])


def test_consumido_buckets_once() -> None:
    """Cada transação num balde só: custo fixo casado > dívida > devolução."""
    spend = [
        SpendTx("a", D("-100"), "expense", "divida"),  # casada a custo fixo: só conta como fixo
        SpendTx("b", D("-50"), "expense", "divida"),
        SpendTx("c", D("-200"), "expense", "consumo"),
        SpendTx("d", D("30"), "income", "devolucao"),
        SpendTx("e", D("1000"), "income", "work_income"),
    ]
    cons = consumido(spend, {"a"})
    assert (cons.gastos, cons.fixos, cons.dividas, cons.devolucoes) == (
        D("350"),
        D("100"),
        D("50"),
        D("30"),
    )
    assert cons.total == D("170")


def test_zero() -> None:
    b = budget(
        BudgetInput(
            trabalho=D(0),
            resgates=D(0),
            custos_fixos=D(0),
            aporte_planejado=None,
            dividas_informadas=None,
            dividas_prefill=D(0),
            consumido=D(0),
        )
    )
    assert (b.disponivel, b.restante, b.consumo_financiado, b.restante_sem_resgates) == (
        D(0),
        D(0),
        D(0),
        D(0),
    )


def test_resgate_covers_everything() -> None:
    # disponível sem resgates = 0; consumido 900 > resgates 500 → financiado = resgates
    assert consumo_financiado(D(500), D(900), D(500)) == D(500)
    b = budget(
        replace(
            _inputs(FIXTURE),
            trabalho=D(0),
            custos_fixos=D(0),
            aporte_planejado=None,
            dividas_informadas=D(0),
        )
    )
    assert b.consumo_financiado == b.resgates_considerados == D("4487.99")


def test_with_devolucao() -> None:
    fx = json.loads(json.dumps(FIXTURE))
    fx["transactions"].append(
        {
            "id": "t_dev",
            "date": "2026-10-12",
            "amount": "100.00",
            "kind": "income",
            "role": "devolucao",
            "group": "Devoluções",
            "description": "Estorno",
            "payer": None,
        }
    )
    b = budget(_inputs(fx))
    assert b.consumido == D("6812.37")
    assert b.restante == D("1593.22")
    assert b.consumo_financiado == D("2894.77")


def test_paid_debt_without_informed_value() -> None:
    """Pagamento em Dívidas com o campo não informado: sai do consumido e entra no disponível (pré-
    preenchido), sem inflar o restante."""
    fx = json.loads(json.dumps(FIXTURE))
    fx["plan"]["dividas"] = None
    fx["transactions"].append(
        {
            "id": "t_div",
            "date": "2026-10-02",
            "amount": "-650.00",
            "kind": "expense",
            "role": "divida",
            "group": "Dívidas",
            "description": "Parcela",
            "payer": None,
        }
    )
    b = budget(_inputs(fx))
    assert b.dividas == D("650.00") and not b.dividas_informadas
    assert b.consumido == D("6912.37")  # a parcela não vira consumo
    assert b.disponivel == D("8405.59")
    assert b.restante == D("1493.22")  # igual ao mockup: não inflou
