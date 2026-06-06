"""§3.1: data de avaliação única.

`service.eval_date` é o seam único do "hoje" do XIRR/valoração. Precedência:
argumento explícito > settings.evaluation_date (env EVALUATION_DATE, p/ reproduzir o
gate / relatórios 'as-of') > date.today(). Sem ele, o XIRR derivava contra seeds com
data fixa e o gate não reproduzia.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from config import settings
from engines.portfolio import service


def test_override_wins() -> None:
    assert service.eval_date(date(2020, 1, 1)) == date(2020, 1, 1)


def test_uses_settings_when_no_override(monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "evaluation_date", date(2024, 3, 2))
    assert service.eval_date(None) == date(2024, 3, 2)
    # override ainda vence sobre a settings
    assert service.eval_date(date(2020, 1, 1)) == date(2020, 1, 1)


def test_falls_back_to_today(monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "evaluation_date", None)
    assert service.eval_date(None) == date.today()
