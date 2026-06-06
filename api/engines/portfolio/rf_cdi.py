"""Valoração de renda fixa PÓS-fixada (% do CDI) — caixinhas/CDB Nubank (pré-m3).

Espelha `rf_pre.py` (pré-fixado), mas indexada ao CDI. Usada para as RDBs/CDBs do
Nubank que rendem um percentual do CDI (Snow Trip 100%, Turbo 115%, CDB Guanabara
117,5%).

    valor_atual = principal * (1 + (pct_cdi/100) * cdi_anual) ^ (dias_corridos / 365)

`cdi_anual` é o CDI anual como fração (ex.: 0.1065 = 10,65% a.a.) e entra como
PARÂMETRO — não há série histórica do CDI ainda (isso é o m5: importação do BCB).
Até lá, o chamador injeta uma constante de referência (settings.cdi_anual). Quando o
m5 importar a série do BCB, troca-se a fonte do `cdi_anual` sem mexer nesta função.
"""

from __future__ import annotations

from datetime import date


def valor_atual_cdi(
    principal: float,
    pct_cdi: float,
    data_inicio: date,
    data_ref: date,
    cdi_anual: float,
) -> float:
    """Valor atual de uma aplicação pós-fixada (% do CDI) na data de referência.

    pct_cdi em % (ex.: 100.0, 115.0, 117.5); cdi_anual em fração (ex.: 0.1065).
    """
    dias = (data_ref - data_inicio).days
    if dias <= 0:
        return principal
    taxa_anual = (pct_cdi / 100.0) * cdi_anual
    return float(principal * (1 + taxa_anual) ** (dias / 365.0))
