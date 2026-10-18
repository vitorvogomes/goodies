"""Story 1.6 — limite de tentativas de login: 5 erradas em 15 min bloqueiam por 15 min."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from auth.rate_limit import LoginLimiter

_T0 = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def test_allows_until_five_failures_then_locks() -> None:
    lim = LoginLimiter()
    for i in range(4):
        lim.record_failure("v@x", _T0 + timedelta(minutes=i))
        assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=i)) == 0
    lim.record_failure("v@x", _T0 + timedelta(minutes=4))
    assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=4)) == 15
    assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=10)) == 9
    assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=18, seconds=30)) == 1
    assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=19)) == 0


def test_failures_outside_window_do_not_count() -> None:
    lim = LoginLimiter()
    for i in range(4):
        lim.record_failure("v@x", _T0 + timedelta(minutes=i))
    lim.record_failure("v@x", _T0 + timedelta(minutes=16))  # as 1ª saiu da janela de 15 min
    assert lim.locked_minutes("v@x", _T0 + timedelta(minutes=16)) == 0


def test_success_resets_and_keys_are_case_insensitive() -> None:
    lim = LoginLimiter()
    for _ in range(4):
        lim.record_failure("V@X", _T0)
    lim.record_success("v@x")
    lim.record_failure("v@x", _T0)
    assert lim.locked_minutes("v@x", _T0) == 0


def test_message_has_minutes() -> None:
    assert LoginLimiter.message(7) == "Muitas tentativas. Tente de novo em 7 minutos."
    assert LoginLimiter.message(1) == "Muitas tentativas. Tente de novo em 1 minuto."
