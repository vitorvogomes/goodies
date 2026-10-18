"""Contrato do Painel principal (AD-15 — Story 4.1)."""

from __future__ import annotations

from pydantic import BaseModel

from engines.common.models import Valued
from engines.common.money import Money, Pct


class Painel(BaseModel):
    periodo: str
    resultado_mes: Valued[Money]
    resultado_mes_anterior: Valued[Money]  # a variação só aparece se o mês anterior existe
    patrimonio: Valued[Money]
    resultado_investimentos: Valued[Money]
    rentabilidade_nominal: Valued[Pct]  # XIRR desde o início até o fim do período, em % a.a.
