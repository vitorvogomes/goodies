"""Story 3.1 — Central de avisos: Alert/AlertContext em common, providers registrados no main,
leitura compute-on-read (divergências antes de avisos, mais recentes primeiro) e dispensa que volta
quando o fingerprint muda."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from engines.alerts import service as alerts_service
from engines.common.alerts import Alert, AlertAction, AlertContext, LegacyAlert, fingerprint
from engines.common.dates import today_brt

URL = "/api/v1/alerts"


def _alert(key: str, severity: str, as_of: date, cond: str = "x") -> Alert:
    return Alert(
        key=key,
        fingerprint=fingerprint(cond),
        severity=severity,  # type: ignore[arg-type]
        message=f"mensagem {key}",
        action=AlertAction(label="Ver", route="/caixa/transacoes", params={"periodo": "2026-10"}),
        as_of=as_of,
    )


def test_fingerprint_is_stable_and_condition_sensitive() -> None:
    assert fingerprint("saldo", "37.20") == fingerprint("saldo", "37.20")
    assert fingerprint("saldo", "37.20") != fingerprint("saldo", "37.21")
    assert LegacyAlert.model_fields.keys() >= {"type", "severity", "title", "message", "data"}


@pytest.fixture
def fake_provider():
    state: dict[str, list[Alert]] = {"alerts": []}

    async def provider(conn, ctx: AlertContext) -> list[Alert]:
        assert ctx.today == today_brt()
        return list(state["alerts"])

    alerts_service.register_alert_provider(provider)
    yield state
    alerts_service.unregister_alert_provider(provider)


@pytest.mark.asyncio
async def test_order_and_shape(api, auth_headers, fake_provider) -> None:
    sfx = uuid.uuid4().hex[:6]
    fake_provider["alerts"] = [
        _alert(f"teste:velho{sfx}", "aviso", date(2026, 10, 1)),
        _alert(f"teste:div{sfx}", "divergencia", date(2026, 9, 1)),
        _alert(f"teste:novo{sfx}", "aviso", date(2026, 10, 15)),
    ]
    r = await api.get(URL, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    mine = [a["key"] for a in body["items"] if a["key"].endswith(sfx)]
    assert mine == [f"teste:div{sfx}", f"teste:novo{sfx}", f"teste:velho{sfx}"]
    assert body["total"] == len(body["items"])
    first = next(a for a in body["items"] if a["key"] == f"teste:div{sfx}")
    assert first["action"] == {
        "label": "Ver",
        "route": "/caixa/transacoes",
        "params": {"periodo": "2026-10"},
    }
    assert "data_until" in body


@pytest.mark.asyncio
async def test_dismiss_until_condition_changes(api, auth_headers, fake_provider, pool) -> None:
    key = f"teste:saldo{uuid.uuid4().hex[:6]}"
    fake_provider["alerts"] = [_alert(key, "divergencia", date(2026, 10, 15), "37.20")]
    a = next(
        x for x in (await api.get(URL, headers=auth_headers)).json()["items"] if x["key"] == key
    )
    d = await api.post(
        f"{URL}/dismissals",
        json={"key": key, "fingerprint": a["fingerprint"]},
        headers=auth_headers,
    )
    assert d.status_code == 204
    keys = [x["key"] for x in (await api.get(URL, headers=auth_headers)).json()["items"]]
    assert key not in keys  # dispensado: não volta com a mesma condição

    fake_provider["alerts"] = [_alert(key, "divergencia", date(2026, 10, 16), "41.00")]
    keys = [x["key"] for x in (await api.get(URL, headers=auth_headers)).json()["items"]]
    assert key in keys  # outra condição (outro valor divergente): volta

    fake_provider["alerts"] = []
    await api.get(URL, headers=auth_headers)
    async with pool.acquire() as conn:
        left = await conn.fetchval("SELECT count(*) FROM alert_dismissals WHERE key = $1", key)
    assert left == 0  # o provider parou de emitir: a dispensa some


@pytest.mark.asyncio
async def test_not_dismissible_is_refused(api, auth_headers, fake_provider) -> None:
    key = f"teste:fixo{uuid.uuid4().hex[:6]}"
    alert = _alert(key, "aviso", date(2026, 10, 15)).model_copy(update={"dismissible": False})
    fake_provider["alerts"] = [alert]
    d = await api.post(
        f"{URL}/dismissals",
        json={"key": key, "fingerprint": alert.fingerprint},
        headers=auth_headers,
    )
    assert d.status_code == 409


@pytest.mark.asyncio
async def test_fixed_cost_due_provider(api, auth_headers, pool) -> None:
    import main  # noqa: F401 — registra os providers

    due = today_brt() + timedelta(days=2)
    name = f"Internet {uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO fixed_costs (name, amount, due_day, category) "
            "VALUES ($1, 99.9, $2, 'Casa')",
            name,
            due.day,
        )
    try:
        items = (await api.get(URL, headers=auth_headers)).json()["items"]
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM fixed_costs WHERE name = $1", name)
    mine = [a for a in items if name in a["message"]]
    assert len(mine) == 1
    a = mine[0]
    assert a["severity"] == "aviso"
    assert a["key"].startswith("custo_fixo_vencendo:")
    assert a["message"] == f"{name} vence em {due.strftime('%d/%m/%Y')}."
    assert a["action"]["label"] == "Ver custos fixos"
    assert a["action"]["route"] == "/ajustes/custos-fixos"


@pytest.mark.asyncio
async def test_v1_cashflow_alerts_still_answer(api, auth_headers) -> None:
    r = await api.get("/api/v1/cashflow/alerts", headers=auth_headers)
    assert r.status_code == 200 and isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_requires_auth(api) -> None:
    assert (await api.get(URL)).status_code == 401
