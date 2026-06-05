"""Valoração de renda fixa PRÉ-fixada (debêntures Flash, CDB pré) — m2.

Fórmula da plataforma Flash (files/debentures-flash/formula.md):
    valor_atual = principal * (1 + fator_mes/100) ^ (dias_corridos / 30)

onde `fator_mes` é o fator mensal em % (ex.: 1,78 para "Pré 24% a.a.") e
`dias_corridos` é o número de dias desde a integralização até a data de referência.
A acumulação diária por dias úteis da planilha equivale, no agregado do período,
a usar dias corridos / 30 (validado contra o snapshot do posicao.json).
"""
from __future__ import annotations

from datetime import date


def valor_atual_pre(
    principal: float,
    fator_mes_pct: float,
    data_inicio: date,
    data_ref: date,
) -> float:
    """Valor atual de uma aplicação pré-fixada na data de referência."""
    dias = (data_ref - data_inicio).days
    if dias <= 0:
        return principal
    return float(principal * (1 + fator_mes_pct / 100) ** (dias / 30))
