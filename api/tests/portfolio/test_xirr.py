"""Tests for XIRR implementation (gate critical)."""
from __future__ import annotations

import math
from datetime import date

from engines.portfolio.xirr import xirr


class TestXIRRBasics:
    """Basic XIRR calculations against Excel reference values."""

    def test_simple_1_year(self) -> None:
        """Buy 2024-01-01, sell 2025-01-01 with 10% gain."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2025, 1, 1), 1100.0),
        ]
        result = xirr(cashflows)
        assert abs(result - 0.10) < 0.001, f"Expected ~0.10, got {result}"

    def test_tesouro_ipca_3_fluxos(self) -> None:
        """3-cashflow bond scenario: buy, coupon, redemption."""
        cashflows = [
            (date(2024, 1, 1), -5000.0),
            (date(2024, 7, 1), 500.0),
            (date(2025, 1, 1), 5300.0),
        ]
        result = xirr(cashflows)
        assert not math.isnan(result), "XIRR should converge"
        assert 0.05 < result < 0.20, f"Expected ~15%, got {result:.2%}"

    def test_cripto_volatile(self) -> None:
        """DCA: 2 buys, 1 sell. High volatility scenario."""
        cashflows = [
            (date(2024, 1, 1), -10000.0),
            (date(2024, 6, 1), -5000.0),
            (date(2024, 12, 1), 18000.0),
        ]
        result = xirr(cashflows)
        assert not math.isnan(result), "XIRR should converge for volatile case"
        assert result > 0.0, "Expected positive return"

    def test_loss_negative_return(self) -> None:
        """Negative return: buy 1000, sell 800 after 1 year."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2025, 1, 1), 800.0),
        ]
        result = xirr(cashflows)
        assert -0.30 < result < -0.15, f"Expected ~-20%, got {result:.2%}"

    def test_ordering_automatic(self) -> None:
        """Out-of-order dates should be auto-sorted."""
        cashflows = [
            (date(2025, 1, 1), 1100.0),
            (date(2024, 1, 1), -1000.0),
        ]
        result = xirr(cashflows)
        assert abs(result - 0.10) < 0.001, "Ordering should be automatic"

    def test_multiple_cashflows_dca(self) -> None:
        """Systematic buying with final position. DCA portfolio scenario."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 4, 1), -1000.0),
            (date(2024, 7, 1), -1000.0),
            (date(2024, 10, 1), -1000.0),
            (date(2025, 1, 1), 4400.0),
        ]
        result = xirr(cashflows)
        assert not math.isnan(result), "XIRR should converge for DCA"
        assert result > 0.0, "Expected positive return (4400 on 4000 invested)"


class TestXIRREdgeCases:
    """Edge cases and error handling."""

    def test_empty_cashflows(self) -> None:
        """Empty list should return nan."""
        result = xirr([])
        assert math.isnan(result), "Empty list should return nan"

    def test_single_cashflow(self) -> None:
        """Single entry (no counterflow) should return nan."""
        result = xirr([(date(2024, 1, 1), 1000.0)])
        assert math.isnan(result), "Single cashflow should return nan"

    def test_non_convergence_returns_nan(self) -> None:
        """Pathological case where solver fails should return nan, not raise."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 0.0),
        ]
        result = xirr(cashflows)
        assert math.isnan(result), "Non-convergence should return nan, not raise"

    def test_zero_net_cashflow(self) -> None:
        """Cashflows that sum to zero."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 6, 1), 500.0),
            (date(2025, 1, 1), 500.0),
        ]
        result = xirr(cashflows)
        assert not math.isnan(result), "Zero net should still converge"
        assert abs(result) < 0.01, "Zero net should be near 0%"

    def test_all_same_date(self) -> None:
        """Multiple cashflows on same date (indeterminate, no time value)."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 1, 1), 1100.0),
        ]
        result = xirr(cashflows)
        assert math.isnan(result), "Same-date flows have no time dimension → nan"

    def test_very_small_gains(self) -> None:
        """Precision test: 0.1% return."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2025, 1, 1), 1001.0),
        ]
        result = xirr(cashflows)
        assert abs(result - 0.001) < 0.0001, f"Expected ~0.1%, got {result:.4%}"

    def test_very_large_return(self) -> None:
        """High return scenario: 100x in 1 year."""
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2025, 1, 1), 100000.0),
        ]
        result = xirr(cashflows)
        assert not math.isnan(result), "High return should converge"
        assert result > 90.0, f"Expected >9000%, got {result:.0%}"
