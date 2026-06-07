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
