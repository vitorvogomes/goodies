"""Termos de dinheiro do portfolio (AD-7 — Story 4.1): uma função pura por termo, em Decimal.

- valor investido = posições + bloco cripto + caixa em corretora (base do XIRR);
- patrimônio = valor investido + saldo das contas;
- resultado dos investimentos = valor investido − aportado líquido + proventos recebidos.
Rendimentos (dividendo, juros) ficam separados do ganho de capital: entram como proventos, não
como aporte.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

INFLOW = frozenset({"compra", "aporte"})
OUTFLOW = frozenset({"venda", "resgate"})
INCOME = frozenset({"dividendo", "juros"})


def _total(op: Mapping[str, Any]) -> Decimal:
    return Decimal(str(op["quantidade"])) * Decimal(str(op["valor_unitario"]))


def net_contributed(ops: Iterable[Mapping[str, Any]]) -> Decimal:
    """Aportado líquido: compras e aportes − vendas e resgates."""
    total = Decimal(0)
    for op in ops:
        if op["tipo"] in INFLOW:
            total += _total(op)
        elif op["tipo"] in OUTFLOW:
            total -= _total(op)
    return total


def income_received(ops: Iterable[Mapping[str, Any]]) -> Decimal:
    """Proventos recebidos (dividendos e juros)."""
    return sum((_total(op) for op in ops if op["tipo"] in INCOME), Decimal(0))


def invested_value(
    *, positions: Decimal, crypto: Decimal, broker_cash: Decimal = Decimal(0)
) -> Decimal:
    return positions + crypto + broker_cash


def patrimony(invested: Decimal, *, accounts: Decimal) -> Decimal:
    return invested + accounts


def investment_result(invested: Decimal, *, contributed: Decimal, income: Decimal) -> Decimal:
    return invested - contributed + income
