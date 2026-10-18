"""Story 5.4 — estado de cada mês (aberto/fechado/ajuste) e o checklist do fechamento: saldo PF
conferido, transações revisadas e as pendências do mês, antes do resumo a congelar."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

URL = "/api/v1/closing/months"


@pytest.mark.asyncio
async def test_month_statuses(api, auth_headers, pool: Any) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ('2024-08-01', 1, 'closed')"
        )
    try:
        r = await api.get(f"{URL}?de=2024-07&ate=2024-09", headers=auth_headers)
        assert r.status_code == 200, r.text
        rows = {m["month"]: m for m in r.json()}
        assert rows["2024-08-01"]["status"] == "fechado" and rows["2024-08-01"]["version"] == 1
        assert rows["2024-07-01"]["status"] == "aberto"
        assert list(rows) == ["2024-07-01", "2024-08-01", "2024-09-01"]
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM month_closes WHERE month = '2024-08-01'")


@pytest.mark.asyncio
async def test_checklist(api, auth_headers) -> None:
    import main  # noqa: F401

    r = await api.get(f"{URL}/2025-04/checklist", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    keys = [i["key"] for i in body["items"]]
    assert keys[:2] == ["saldo_pf", "revisadas"]
    assert all(set(i) >= {"key", "ok", "kind", "message"} for i in body["items"])
    assert body["summary"]["as_of"] == "2025-04-30"
    assert body["blocking"] == sum(
        1 for i in body["items"] if i["kind"] == "bloqueia" and not i["ok"]
    )


@pytest.mark.asyncio
async def test_checklist_codes_close_the_month(api, auth_headers, pool: Any) -> None:
    """Os códigos do checklist são os que `close` aceita em `confirmar`."""
    import main  # noqa: F401

    body = (await api.get(f"{URL}/2025-05/checklist", headers=auth_headers)).json()
    if body["blocking"]:
        return
    codes = [i["code"] for i in body["items"] if not i["ok"] and i["kind"] == "confirma"]
    try:
        r = await api.post(f"{URL}/2025-05/close", json={"confirmar": codes}, headers=auth_headers)
        assert r.status_code == 201, r.text
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM month_closes WHERE month = $1", date(2025, 5, 1))
