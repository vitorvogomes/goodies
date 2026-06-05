"""XIRR implementation for portfolio return calculation (gate critical m2)."""
from __future__ import annotations

from datetime import date

from scipy.optimize import brentq  # type: ignore[import-untyped]


def xirr(cashflows: list[tuple[date, float]]) -> float:
    """
    Calculate Internal Rate of Return (XIRR) from dated cashflows.

    Args:
        cashflows: List of (date, amount) tuples. Purchases negative, sales/gains positive.

    Returns:
        Annualized decimal rate (e.g., 0.0853 = 8.53% p.a.). Returns float('nan')
        if less than 2 flows, dates identical, or solver fails.

    Edge cases:
        - Empty list or single flow: returns nan
        - Zero net cashflow: converges to ~0%
        - Non-convergent cases: returns nan (no exception raised)
    """
    if len(cashflows) < 2:
        return float("nan")

    sorted_cf = sorted(cashflows, key=lambda x: x[0])
    dates, amounts = zip(*sorted_cf, strict=True)
    t0 = dates[0]
    days = [(d - t0).days for d in dates]

    def npv(r: float) -> float:
        return sum(  # type: ignore[no-any-return]
            a / (1 + r) ** (d / 365) for a, d in zip(amounts, days, strict=True)
        )

    try:
        return brentq(npv, -0.999, 100.0, xtol=1e-8, maxiter=1000)  # type: ignore[no-any-return]
    except ValueError:
        return float("nan")
