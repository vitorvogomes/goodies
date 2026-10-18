"""Termos de dinheiro do portfolio (AD-7 — Story 4.1): uma função pura por termo, em Decimal.

- valor investido = posições + bloco cripto + caixa em corretora (base do XIRR);
- patrimônio = valor investido + saldo das contas;
- resultado dos investimentos = valor investido − aportado líquido + proventos recebidos.
Rendimentos (dividendo, juros) ficam separados do ganho de capital: entram como proventos, não
como aporte.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
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


def quantity(ops: Iterable[Mapping[str, Any]]) -> Decimal:
    """Quantidade líquida: compras e aportes − vendas e resgates."""
    total = Decimal(0)
    for op in ops:
        q = Decimal(str(op["quantidade"]))
        if op["tipo"] in INFLOW:
            total += q
        elif op["tipo"] in OUTFLOW:
            total -= q
    return total


def period_result(
    value_end: Decimal, value_start: Decimal, *, flows: Decimal, income: Decimal
) -> Decimal:
    """Resultado de um período (Story 7.1): valor no fim − valor no início − aportado líquido no
    período + proventos no período. Desde o início, é o `investment_result`."""
    return value_end - value_start - flows + income


# --------------------------------------------------------------------------------------------
# Rentabilidade de um período (Story 7.3 — XIRR, nunca (resultado − aplicado) / aplicado)
# --------------------------------------------------------------------------------------------


def period_xirr(
    start_value: Decimal,
    start_day: date,
    flows: Iterable[tuple[date, Decimal]],
    end_value: Decimal,
    end_day: date,
) -> float | None:
    """XIRR do período: o valor investido no início entra como aporte (negativo) no dia anterior
    ao período, os fluxos líquidos datados (aporte < 0, venda/provento > 0) e o valor no fim como
    saída. Sem valor nem fluxo, ou sem convergência → None."""
    from .xirr import xirr

    cashflows: list[tuple[date, float]] = []
    if start_value:
        cashflows.append((start_day, -float(start_value)))
    cashflows += [(d, float(v)) for d, v in flows if v]
    if end_value:
        cashflows.append((end_day, float(end_value)))
    if len(cashflows) < 2 or all(v >= 0 for _, v in cashflows) or all(v <= 0 for _, v in cashflows):
        return None
    rate = xirr(cashflows)
    return None if rate != rate else rate  # NaN → sem convergência


def ipca_factor(monthly_pct: Iterable[Decimal]) -> Decimal:
    """IPCA efetivo do período: Π(1 + IPCA do mês / 100)."""
    factor = Decimal(1)
    for m in monthly_pct:
        factor *= 1 + m / 100
    return factor


def real_rate(nominal_annual: float, ipca_period_factor: Decimal, days: int) -> float:
    """Taxa real anual (Fisher): (1 + nominal) / (1 + IPCA anualizado do período) − 1."""
    ipca_annual: float = float(ipca_period_factor) ** (365 / max(days, 1)) - 1
    return float((1 + nominal_annual) / (1 + ipca_annual) - 1)


def monthly_rate(annual: float) -> float:
    """Taxa anual → ao mês: (1 + a)^(1/12) − 1."""
    return float((1 + annual) ** (1 / 12) - 1)


def signed_flow(op: Mapping[str, Any]) -> Decimal:
    """Fluxo de uma operação no sinal do XIRR: aporte/compra < 0; venda/resgate/provento > 0."""
    total = _total(op)
    if op["tipo"] in INFLOW:
        return -total
    if op["tipo"] in OUTFLOW or op["tipo"] in INCOME:
        return total
    return Decimal(0)


# --------------------------------------------------------------------------------------------
# Caixa em corretora × a caminho (Story 7.7 — AD-7)
# --------------------------------------------------------------------------------------------

RESIDUAL_TOLERANCE = Decimal("1.00")  # abaixo disso o trilho está conciliado


def broker_split(
    residual: Decimal,
    transfers: Iterable[tuple[date, Decimal]],
    covered_until: date | None,
) -> tuple[Decimal, Decimal]:
    """(caixa em corretora, a caminho) do resíduo da corretora (saiu + proventos − aplicado).

    As transferências para a corretora com data depois do "atualizado até" do relatório dela
    ainda não viraram posição no que o app vê: são a caminho (fora do patrimônio), até o
    resíduo. O resto do resíduo é caixa parado na corretora (no patrimônio). Resíduo dentro da
    tolerância (ou negativo) → nada."""
    if residual <= RESIDUAL_TOLERANCE:
        return Decimal(0), Decimal(0)
    pending = sum(
        (amount for day, amount in transfers if covered_until is None or day > covered_until),
        Decimal(0),
    )
    on_the_way = min(residual, max(pending, Decimal(0)))
    return residual - on_the_way, on_the_way
