"""Story 2.1 (A13) — "hoje" e limites de mês só por `common.dates`: nada de `date.today()`,
`datetime.now()` sem fuso, `utcnow()`, `CURRENT_DATE` ou `now()::date` no código da api."""

from __future__ import annotations

import re
from pathlib import Path

API = Path(__file__).resolve().parents[2]
SCAN = ["engines", "workers", "auth", "hermes", "db", "scripts/ops", "main.py", "config.py"]
ALLOWED = {"engines/common/dates.py"}
PATTERNS = [
    re.compile(r"\bdate\.today\(\)"),
    re.compile(r"\bdatetime\.now\(\s*\)"),
    re.compile(r"\butcnow\(\)"),
    re.compile(r"CURRENT_DATE", re.I),
    re.compile(r"now\(\)::date", re.I),
]


def _files() -> list[Path]:
    out: list[Path] = []
    for item in SCAN:
        p = API / item
        out += [p] if p.is_file() else sorted(p.rglob("*.py"))
    return [f for f in out if "__pycache__" not in f.parts]


def test_no_naive_today_outside_common_dates() -> None:
    found = []
    for f in _files():
        rel = f.relative_to(API).as_posix()
        if rel in ALLOWED:
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if any(p.search(code) for p in PATTERNS) and '"""' not in line:
                found.append(f"{rel}:{i}: {line.strip()}")
    assert found == [], "\n".join(found)
