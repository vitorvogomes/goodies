"""Contrato do Painel principal (AD-15 — Story 4.1)."""

from __future__ import annotations

from pydantic import BaseModel

from engines.common.models import Valued
from engines.common.money import Money, Pct
from engines.ingest.models import SourceRow


class Painel(BaseModel):
    periodo: str
    resultado_mes: Valued[Money]
    resultado_mes_anterior: Valued[Money]  # a variação só aparece se o mês anterior existe
    patrimonio: Valued[Money]
    resultado_investimentos: Valued[Money]
    rentabilidade_nominal: Valued[Pct]  # XIRR desde o início até o fim do período, em % a.a.
    a_revisar: int  # transações pendentes de revisão (Story 4.2)


class Fonte(SourceRow):
    """Linha do Bloco Fontes do Painel: as de arquivo abrem o Hub; as automáticas, não."""

    opens_hub: bool
