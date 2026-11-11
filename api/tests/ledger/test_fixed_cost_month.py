"""Story 6.2 — Caixa › Custos fixos: lista do mês com Selo (pago, pendente, vencendo, atrasado,
manual) e transação casada, ordem atrasado → pago, cabeçalho pago × pendente; decisões gravadas em
`fixed_cost_payments` (Confirmar, Trocar, Marcar pago manualmente, Desfazer); "2 candidatas"; mês
fechado só leitura."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.ledger import service as ledger

URL = "/api/v1/ledger/fixed-costs"
MONTH = date(2097, 5, 1)


async def _seed(pool: Any, account: str) -> dict[str, str]:
    async with pool.acquire() as conn:
        cat = await conn.fetchval(
            "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
        )
        ids: dict[str, str] = {}
        for key, amount, day in (("luz", "200", 5), ("plano", "450", 10), ("net", "100", 28)):
            ids[key] = str(
                await conn.fetchval(
                    "INSERT INTO fixed_costs (name, amount, due_day, category_id, valid_from) "
                    "VALUES ($1, $2, $3, $4, '2097-01-01') RETURNING id",
                    f"{key} {uuid.uuid4().hex[:4]}",
                    Decimal(amount),
                    day,
                    cat,
                )
            )
        for key, amount, day in (
            ("t_luz", "-201.00", 6),
            ("t_p1", "-450.00", 9),
            ("t_p2", "-452.00", 12),
        ):
            ids[key] = str(
                await conn.fetchval(
                    "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
                    "description) VALUES ($1::uuid, $2, $3, $4, 'expense', $5) RETURNING id",
                    account,
                    date(2097, 5, day),
                    Decimal(amount),
                    cat,
                    key,
                )
            )
    return ids


@pytest.mark.asyncio
async def test_month_list_and_decisions(api, auth_headers, pool, account) -> None:
    ids = await _seed(pool, account)
    async with pool.acquire() as conn:
        view = await ledger.fixed_cost_month(conn, MONTH, today=date(2097, 5, 26))
    by = {i.id: i for i in view.items}
    assert by[ids["luz"]].status == "pago" and by[ids["luz"]].transaction.id == ids["t_luz"]
    assert by[ids["plano"]].status == "atrasado"  # 2 candidatas e vencido: nada pago
    assert sorted(c.id for c in by[ids["plano"]].candidates) == sorted([ids["t_p1"], ids["t_p2"]])
    assert by[ids["net"]].status == "vencendo"  # vence em 2 dias
    assert [i.status for i in view.items] == ["atrasado", "vencendo", "pago"]
    assert (view.paid_count, view.count) == (1, 3)
    assert view.paid_total == Decimal("201.00") and view.total == Decimal("750.00")
    # v2.2: pago × previsto — luz previa 200 e saiu 201 (R$ 1 a mais); só os pagos com transação
    luz = by[ids["luz"]]
    assert (luz.paid_amount, luz.difference) == (Decimal("201.00"), Decimal("-1.00"))
    assert by[ids["net"]].paid_amount is None and by[ids["net"]].difference is None
    assert (view.paid_expected, view.difference_total) == (Decimal("200"), Decimal("-1.00"))

    mes = "2097-05"
    r = await api.post(
        f"{URL}/{ids['plano']}/decisions",
        json={"mes": mes, "kind": "confirmado", "transaction_id": ids["t_p2"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    r = await api.post(
        f"{URL}/{ids['net']}/decisions", json={"mes": mes, "kind": "manual"}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    r = await api.post(
        f"{URL}/{ids['luz']}/decisions",
        json={"mes": mes, "kind": "desfeito", "transaction_id": ids["t_luz"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = (await api.get(f"{URL}/month?periodo={mes}", headers=auth_headers)).json()
    status = {i["id"]: (i["status"], (i["transaction"] or {}).get("id")) for i in body["items"]}
    assert status[ids["plano"]] == ("pago", ids["t_p2"])
    assert status[ids["net"]] == ("manual", None)
    assert status[ids["luz"]][0] in ("pendente", "atrasado") and status[ids["luz"]][1] is None
    r = await api.delete(f"{URL}/{ids['net']}/decisions/{mes}", headers=auth_headers)
    assert r.status_code == 204
    async with pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM fixed_cost_payments WHERE fixed_cost_id = $1::uuid", ids["net"]
        )


@pytest.mark.asyncio
async def test_undo_accumulates_and_confirm_replaces(api, auth_headers, pool, account) -> None:
    """P13: desfazer uma candidata não traz de volta a desfeita antes; confirmar depois de desfazer
    paga e a transação confirmada sai das desfeitas."""
    ids = await _seed(pool, account)
    mes, url = "2097-05", f"{URL}/{ids['plano']}/decisions"
    for tx in ("t_p1", "t_p2"):
        r = await api.post(
            url,
            json={"mes": mes, "kind": "desfeito", "transaction_id": ids[tx]},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        view = await ledger.fixed_cost_month(conn, MONTH, today=date(2097, 5, 26))
        item = next(i for i in view.items if i.id == ids["plano"])
        assert item.transaction is None and item.candidates == []
    r = await api.post(
        url,
        json={"mes": mes, "kind": "confirmado", "transaction_id": ids["t_p1"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        kinds = sorted(
            r["kind"]
            for r in await conn.fetch(
                "SELECT kind FROM fixed_cost_payments WHERE fixed_cost_id = $1::uuid", ids["plano"]
            )
        )
        assert kinds == ["confirmado", "desfeito"]


@pytest.mark.asyncio
async def test_closed_month_is_read_only(api, auth_headers, pool, account) -> None:
    ids = await _seed(pool, account)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ($1, 1, 'closed')", MONTH
        )
    try:
        r = await api.post(
            f"{URL}/{ids['net']}/decisions",
            json={"mes": "2097-05", "kind": "manual"},
            headers=auth_headers,
        )
        assert r.status_code == 409 and r.json()["detail"]["error"] == "mes_fechado"
        body = (await api.get(f"{URL}/month?periodo=2097-05", headers=auth_headers)).json()
        assert body["closed"] is True
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM month_closes WHERE month = $1", MONTH)


@pytest.mark.asyncio
async def test_due_and_late_alerts(pool, account) -> None:
    """Story 6.3: sem pagamento casado, "{Custo} vence em {dd/mm/aaaa}." (faltando ≤ 3 dias) e,
    vencido, "{Custo} atrasado desde {dd/mm/aaaa}.", com Ver custos fixos; pago não avisa."""
    import main  # noqa: F401
    from engines.common.alerts import AlertContext
    from engines.common.month_status import month_status

    ids = await _seed(pool, account)
    async with pool.acquire() as conn:
        names = {
            str(r["id"]): r["name"]
            for r in await conn.fetch(
                "SELECT id, name FROM fixed_costs WHERE id = ANY($1::uuid[])",
                [ids["luz"], ids["plano"], ids["net"]],
            )
        }
        ctx = AlertContext(
            today=date(2097, 5, 26), periodo=MONTH, months=month_status(), owner_id="x"
        )
        alerts = {a.key: a for a in await ledger.fixed_cost_alerts(conn, ctx)}
    late = alerts[f"custo_fixo:{ids['plano']}:2097-05"]
    assert late.message == f"{names[ids['plano']]} atrasado desde 10/05/2097."
    soon = alerts[f"custo_fixo:{ids['net']}:2097-05"]
    assert soon.message == f"{names[ids['net']]} vence em 28/05/2097."
    assert soon.action.label == "Ver custos fixos" and soon.action.route == "/caixa/custos-fixos"
    assert f"custo_fixo:{ids['luz']}:2097-05" not in alerts  # pago
