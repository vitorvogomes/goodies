"""Resumo do mês (AD-8 — Story 5.2): os termos da AD-7 de um mês, ao vivo (e, a partir da 5.3,
congelados no fechamento)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from engines.common.money import Money, Pct


class MonthSummary(BaseModel):
    month: date
    as_of: date  # fim do mês, ou hoje no mês corrente
    source: str = "live"
    # caixa (ledger/calc)
    receitas: Money
    trabalho: Money
    resgates: Money
    devolucoes: Money
    gastos: Money
    investido: Money
    taxa_poupanca: Pct | None  # em %
    resultado_mes: Money
    receitas_por_pagador: dict[str, Money]
    gastos_por_categoria: dict[str, Money]
    ledger_as_of: date | None
    income_as_of: date | None  # trabalho/poupança: o MEI pode não cobrir o mês
    income_stale: bool
    saldo_conferido_pf: bool | None
    # investimentos (portfolio/calc)
    saldo_contas: Money
    valor_investido: Money
    patrimonio: Money
    aplicado: Money
    resultado_investimentos: Money
    rentabilidade: Pct | None  # XIRR desde o início até as_of, em % a.a.
    valor_por_classe: dict[str, Money]
    valor_por_ativo: dict[str, Money]
    portfolio_as_of: date | None
    portfolio_stale: bool
    coverage: dict[str, str]  # fonte → método de valoração ("B3: consolidado de 30/09/2026")
