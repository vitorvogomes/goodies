"""Tests for RF pós-fixada (% do CDI) valuation — caixinhas/CDB Nubank (pré-m3).

Espelha test_rf_pre.py. CDI anual é parâmetro (constante provisória até o m5
importar a série do BCB). Fórmula: principal * (1 + (pct_cdi/100)*cdi_anual) ^ (dias/365).
"""

from __future__ import annotations

from datetime import date

from engines.portfolio.rf_cdi import valor_atual_cdi


class TestValorAtualCdi:
    def test_no_elapsed_time_returns_principal(self) -> None:
        d = date(2026, 6, 1)
        assert valor_atual_cdi(1000.0, 100.0, d, d, 0.1065) == 1000.0

    def test_future_before_start_returns_principal(self) -> None:
        assert valor_atual_cdi(1000.0, 100.0, date(2026, 6, 1), date(2026, 5, 1), 0.1065) == 1000.0

    def test_one_year_100pct_cdi(self) -> None:
        """365 dias a 100% do CDI ≈ principal*(1+cdi_anual)."""
        v = valor_atual_cdi(1000.0, 100.0, date(2025, 6, 1), date(2026, 6, 1), 0.1065)
        assert abs(v - 1106.5) < 0.5

    def test_115pct_beats_100pct(self) -> None:
        """Caixinha Turbo (115% CDI) rende mais que 100% na mesma janela."""
        start, ref = date(2025, 6, 1), date(2026, 6, 1)
        v100 = valor_atual_cdi(1000.0, 100.0, start, ref, 0.1065)
        v115 = valor_atual_cdi(1000.0, 115.0, start, ref, 0.1065)
        assert v115 > v100

    def test_117_5pct_guanabara(self) -> None:
        """CDB Guanabara (117,5% CDI) — 1 ano rende ~117,5% do CDI."""
        v = valor_atual_cdi(200.0, 117.5, date(2025, 6, 1), date(2026, 6, 1), 0.1065)
        # 200 * (1 + 1.175*0.1065) = 200 * 1.1251 ≈ 225.03
        assert abs(v - 225.03) < 0.5

    def test_proportional_to_principal(self) -> None:
        start, ref = date(2025, 6, 1), date(2026, 6, 1)
        v1 = valor_atual_cdi(1000.0, 100.0, start, ref, 0.1065)
        v2 = valor_atual_cdi(2000.0, 100.0, start, ref, 0.1065)
        assert abs(v2 - 2 * v1) < 1e-6
