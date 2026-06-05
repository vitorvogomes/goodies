"""Tests for RF pré-fixada valuation (debêntures Flash — STORY-02-17-18)."""
from __future__ import annotations

from datetime import date

from engines.portfolio.rf_pre import valor_atual_pre


class TestValorAtualPre:
    def test_no_elapsed_time_returns_principal(self) -> None:
        d = date(2026, 6, 1)
        assert valor_atual_pre(1000.0, 1.78, d, d) == 1000.0

    def test_future_before_start_returns_principal(self) -> None:
        assert valor_atual_pre(
            1000.0, 1.78, date(2026, 6, 1), date(2026, 5, 1)
        ) == 1000.0

    def test_one_year_approx_24pct(self) -> None:
        """1,78%/mês compõe ~24% a.a. (fator mensal sobre dias/30)."""
        v = valor_atual_pre(1000.0, 1.78, date(2025, 6, 1), date(2026, 6, 1))
        # (1.0178)^(365/30) ≈ 1.239
        assert 1230.0 < v < 1245.0

    def test_one_month_is_factor(self) -> None:
        v = valor_atual_pre(1000.0, 1.78, date(2026, 5, 1), date(2026, 5, 31))
        # 30 dias -> ~1.0178
        assert abs(v - 1017.8) < 1.0
