"""Helper de data no fuso BRT — corrige off-by-one dos alertas em prod UTC (débito m4)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from engines.common.dates import today_brt


def test_today_brt_late_night_utc_is_previous_brt_day() -> None:
    # 01:00 UTC do dia 8 == 22:00 BRT do dia 7 → "hoje" em BRT ainda é o dia 7.
    moment = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    assert today_brt(moment) == date(2026, 6, 7)


def test_today_brt_default_matches_sao_paulo_now() -> None:
    assert today_brt() == datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def test_resolve_period_matches_web() -> None:
    from engines.common.dates import resolve_period

    d = date
    assert resolve_period("2026-10", "mes") == [d(2026, 10, 1)]
    assert resolve_period("2026-11", "tri") == [d(2026, 10, 1), d(2026, 11, 1)]
    assert resolve_period("2026-04", "ano") == [d(2026, m, 1) for m in range(1, 5)]
    inicio = resolve_period("2025-01", "inicio")
    assert inicio[0] == d(2024, 7, 1) and inicio[-1] == d(2025, 1, 1) and len(inicio) == 7
    assert resolve_period("2024-09", "ano") == [d(2024, 7, 1), d(2024, 8, 1), d(2024, 9, 1)]


def test_resolve_period_rejects_bad_input() -> None:
    import pytest

    from engines.common.dates import resolve_period

    for bad in ("2026-13", "26-01", ""):
        with pytest.raises(ValueError):
            resolve_period(bad, "mes")
    with pytest.raises(ValueError):
        resolve_period("2026-01", "semestre")
