"""Story 4.1 — termos de dinheiro do portfolio (AD-7): uma função pura por termo."""

from __future__ import annotations

from decimal import Decimal as D

from engines.portfolio.calc import (
    income_received,
    invested_value,
    investment_result,
    net_contributed,
    patrimony,
)

OPS = [
    {"tipo": "compra", "quantidade": D("10"), "valor_unitario": D("5")},  # +50
    {"tipo": "aporte", "quantidade": D("100"), "valor_unitario": D("1")},  # +100
    {"tipo": "venda", "quantidade": D("2"), "valor_unitario": D("6")},  # −12
    {"tipo": "resgate", "quantidade": D("30"), "valor_unitario": D("1")},  # −30
    {"tipo": "dividendo", "quantidade": D("1"), "valor_unitario": D("4")},  # provento
    {"tipo": "juros", "quantidade": D("1"), "valor_unitario": D("1.5")},  # provento
]


def test_contributions_and_income() -> None:
    assert net_contributed(OPS) == D("108")
    assert income_received(OPS) == D("5.5")


def test_invested_value_patrimony_and_result() -> None:
    invested = invested_value(positions=D("200"), crypto=D("50"))
    assert invested == D("250")
    assert invested_value(positions=D("200"), crypto=D("50"), broker_cash=D("7")) == D("257")
    assert patrimony(invested, accounts=D("1000")) == D("1250")
    # resultado = valor − aportado líquido + proventos recebidos
    assert investment_result(invested, contributed=D("158"), income=D("5.5")) == D("97.5")
