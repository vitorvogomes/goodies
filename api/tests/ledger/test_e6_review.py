"""Revisão do Épico 6 (custos fixos): Trocar honra a saída escolhida do mês fora da janela; decisão
inválida ou transação em uso não vira 500; a janela não cruza o mês; excluir encerra a vigência no
mês anterior; aviso "vence em" olha o mês seguinte; v1 desativar encerra a vigência."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.common.alerts import AlertContext
from engines.common.dates import add_months, today_brt
from engines.common.month_status import month_status
from engines.ledger import service as ledger

URL = "/api/v1/ledger/fixed-costs"


async def _cat(conn: Any) -> Any:
    return await conn.fetchval(
        "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
        "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
    )


async def _cost(conn: Any, amount: str, day: int, valid_from: date) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO fixed_costs (name, amount, due_day, category, category_id, valid_from) "
            "VALUES ($1, $2, $3, 'x', $4, $5) RETURNING id",
            f"Custo {uuid.uuid4().hex[:6]}",
            Decimal(amount),
            day,
            await _cat(conn),
            valid_from,
        )
    )


async def _tx(conn: Any, account: str, d: date, amount: str, kind: str = "expense") -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description) VALUES ($1::uuid, $2, $3, 'x', $4, $5, 't') RETURNING id",
            account,
            d,
            Decimal(amount),
            await _cat(conn),
            kind,
        )
    )


@pytest.mark.asyncio
async def test_trocar_outside_window_and_invalid_decisions(
    api, auth_headers, pool, account
) -> None:
    async with pool.acquire() as conn:
        a = await _cost(conn, "100", 10, date(2094, 1, 1))
        b = await _cost(conn, "100", 12, date(2094, 1, 1))
        far = await _tx(conn, account, date(2094, 6, 25), "-130.00")  # fora da janela e do ±10%
        other_month = await _tx(conn, account, date(2094, 7, 2), "-100.00")
    r = await api.post(
        f"{URL}/{a}/decisions",
        json={"mes": "2094-06", "kind": "corrigido", "transaction_id": far},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i["id"] == a)
    assert (item["status"], item["transaction"]["id"]) == ("pago", far)
    r = await api.post(
        f"{URL}/{b}/decisions",
        json={"mes": "2094-06", "kind": "corrigido", "transaction_id": far},
        headers=auth_headers,
    )
    assert r.status_code == 409 and r.json()["detail"]["error"] == "transacao_em_uso"
    for tx in (other_month, str(uuid.uuid4())):
        r = await api.post(
            f"{URL}/{b}/decisions",
            json={"mes": "2094-06", "kind": "corrigido", "transaction_id": tx},
            headers=auth_headers,
        )
        assert r.status_code == 422 and r.json()["detail"]["error"] == "decisao_invalida"


@pytest.mark.asyncio
async def test_window_does_not_cross_month(pool, account) -> None:
    async with pool.acquire() as conn:
        cost = await _cost(conn, "200", 2, date(2094, 1, 1))
        paid_before = await _tx(conn, account, date(2094, 8, 30), "-200.00")
        aug = {m.cost_id: m for m in await ledger.fixed_cost_matches(conn, date(2094, 8, 1))}
        sep = {m.cost_id: m for m in await ledger.fixed_cost_matches(conn, date(2094, 9, 1))}
        facts = await ledger.budget_facts(conn, date(2094, 8, 1))
    assert sep[cost].transaction_id != paid_before  # pagamento de agosto não paga setembro
    assert aug[cost].transaction_id is None  # nem o vencimento de 02/08
    assert facts.consumed.total >= Decimal("200.00")  # fica no consumido do próprio mês, uma vez


@pytest.mark.asyncio
async def test_delete_ends_vigencia_last_month(api, auth_headers, pool) -> None:
    current = today_brt().replace(day=1)
    async with pool.acquire() as conn:
        old = await _cost(conn, "50", 5, date(2025, 1, 1))
    assert (await api.delete(f"{URL}/{old}", headers=auth_headers)).status_code == 204
    async with pool.acquire() as conn:
        valid_to = await conn.fetchval("SELECT valid_to FROM fixed_costs WHERE id = $1::uuid", old)
        due_now = {str(r["id"]) for r in await ledger.fixed_costs_due(conn, current)}
    assert valid_to == add_months(current, -1) and old not in due_now
    listed = {c["id"] for c in (await api.get(URL, headers=auth_headers)).json()}
    assert old not in listed


@pytest.mark.asyncio
async def test_due_soon_looks_into_next_month(pool) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        cost = await _cost(conn, "70", 1, date(2094, 1, 1))
        ctx = AlertContext(
            today=date(2094, 10, 30), periodo=date(2094, 10, 1), months=month_status(), owner_id="x"
        )
        alerts = {a.key: a for a in await ledger.fixed_cost_alerts(conn, ctx)}
    assert alerts[f"custo_fixo:{cost}:2094-11"].message.endswith("vence em 01/11/2094.")


@pytest.mark.asyncio
async def test_v1_deactivate_ends_vigencia(api, auth_headers, pool) -> None:
    current = today_brt().replace(day=1)
    async with pool.acquire() as conn:
        cost = await _cost(conn, "80", 8, date(2025, 1, 1))
    r = await api.put(
        f"/api/v1/fixed-costs/{cost}", json={"is_active": False}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    async with pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT valid_to FROM fixed_costs WHERE id = $1::uuid", cost
        ) == add_months(current, -1)
    await api.put(f"/api/v1/fixed-costs/{cost}", json={"is_active": True}, headers=auth_headers)
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT valid_to FROM fixed_costs WHERE id = $1::uuid", cost)
            is None
        )
