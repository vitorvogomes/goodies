"""Limite de tentativas de login (Story 1.6 — AD-18).

5 tentativas erradas em 15 minutos bloqueiam o e-mail por 15 minutos, contados da 5ª falha. Estado
em memória do processo: a api local é um processo só (ADR-003); reiniciar zera o contador.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timedelta

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
LOCK = timedelta(minutes=15)


class LoginLimiter:
    def __init__(self) -> None:
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._locked_until: dict[str, datetime] = {}

    @staticmethod
    def _key(email: str) -> str:
        return email.strip().lower()

    def locked_minutes(self, email: str, now: datetime) -> int:
        until = self._locked_until.get(self._key(email))
        if until is None or now >= until:
            return 0
        return math.ceil((until - now).total_seconds() / 60)

    def record_failure(self, email: str, now: datetime) -> None:
        key = self._key(email)
        recent = self._failures[key]
        recent.append(now)
        while recent and now - recent[0] > WINDOW:
            recent.popleft()
        if len(recent) >= MAX_FAILURES:
            self._locked_until[key] = now + LOCK
            recent.clear()

    def record_success(self, email: str) -> None:
        key = self._key(email)
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    @staticmethod
    def message(minutes: int) -> str:
        unit = "minuto" if minutes == 1 else "minutos"
        return f"Muitas tentativas. Tente de novo em {minutes} {unit}."


login_limiter = LoginLimiter()
