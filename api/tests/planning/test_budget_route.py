"""Story 6.5 — o orçamento pela rota de `closing` com os insumos do mockup gravados no banco: o
pipeline (transações por papel, casamento de custos fixos, `month_plans`) dá os mesmos números do
golden; a escrita das dívidas por `planning` volta ao pré-preenchido com `null` e é recusada em mês
fechado."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "mockup_out2026.json").read_text(encoding="utf-8")
)
YEAR = 2095  # o mês do mockup (out) num ano sem outros dados no goodies_test
MES = f"{YEAR}-10"
MONTH = date(YEAR, 10, 1)


@pytest.fixture
async def seeded(pool: Any, account: str):
    async with pool.acquire() as conn:
        role_cat = {
            r["role"]: r["id"]
            for r in await conn.fetch(
                "SELECT DISTINCT ON (c.role) c.role, c.id FROM categories c "
                "JOIN category_groups g ON g.id = c.group_id WHERE NOT g.is_system "
                "ORDER BY c.role, c.key"
            )
        }
        for t in FIXTURE["transactions"]:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
                "description, payer) VALUES ($1::uuid, $2, $3, 'x', $4, $5, $6, $7)",
                account,
                date.fromisoformat(t["date"]).replace(year=YEAR),
                Decimal(t["amount"]),
                role_cat[t["role"]],
                t["kind"],
                t["description"],
                t["payer"],
            )
        costs = []
        for c in FIXTURE["fixed_costs"]:
            costs.append(
                await conn.fetchval(
                    "INSERT INTO fixed_costs (name, amount, due_day, category, category_id, "
                    "valid_from) VALUES ($1, $2, $3, 'x', $4, $5) RETURNING id",
                    f"{c['name']} {uuid.uuid4().hex[:4]}",
                    Decimal(c["amount"]),
                    c["due_day"],
                    role_cat["consumo"],
                    date(YEAR, 1, 1),
                )
            )
        await conn.execute(
            "INSERT INTO month_plans (month, dividas, aporte_planejado) VALUES ($1, $2, $3)",
            MONTH,
            Decimal(FIXTURE["plan"]["dividas"]),
            Decimal(FIXTURE["plan"]["aporte_planejado"]),
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM month_plans WHERE month = $1", MONTH)
        await conn.execute("DELETE FROM month_closes WHERE month = $1", MONTH)
        await conn.execute("DELETE FROM fixed_costs WHERE id = ANY($1::uuid[])", costs)


@pytest.mark.asyncio
async def test_budget_route_matches_golden(api, auth_headers, seeded) -> None:
    import main  # noqa: F401

    exp = FIXTURE["expected"]
    r = await api.get(f"/api/v1/closing/months/{MES}/budget", headers=auth_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    for term in ("disponivel", "consumido", "restante", "consumo_financiado"):
        assert Decimal(str(b[term]["value"])) == Decimal(exp[term]), term
    assert Decimal(str(b["custos_fixos"]["value"])) == Decimal(exp["custos_fixos"])
    assert Decimal(str(b["custos_fixos_pagos"])) == Decimal(exp["custos_fixos_pagos"])
    assert Decimal(str(b["taxa_poupanca"]["value"])) == Decimal(exp["taxa_poupanca_pct"])
    assert Decimal(str(b["aporte_sobre_trabalho"]["value"])) == Decimal(
        exp["aporte_sobre_trabalho_pct"]
    )
    assert [p["payer"] for p in b["trabalho_por_pagador"]] == ["Flash", "Betuel"]
    assert b["dividas_informadas"] is True and b["source"] == "live"


@pytest.mark.asyncio
async def test_dividas_write(api, auth_headers, pool, seeded) -> None:
    import main  # noqa: F401

    url = f"/api/v1/planning/months/{MES}/dividas"
    r = await api.put(url, json={"valor": None}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["dividas"] is None
    b = (await api.get(f"/api/v1/closing/months/{MES}/budget", headers=auth_headers)).json()
    assert b["dividas_informadas"] is False and b["dividas"] == 0.0  # sem transações em Dívidas
    assert Decimal(str(b["disponivel"]["value"])) == Decimal("9055.59")  # sem os 650
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ($1, 1, 'closed')", MONTH
        )
    r = await api.put(url, json={"valor": "100.00"}, headers=auth_headers)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "mes_fechado"


@pytest.mark.asyncio
async def test_no_work_income_is_unavailable(api, auth_headers) -> None:
    """Story 6.7: sem receita do trabalho, taxa de poupança e aporte ÷ trabalho voltam `Valued` nulo
    com `sem_receita` — nunca 0%."""
    b = (await api.get("/api/v1/closing/months/2093-03/budget", headers=auth_headers)).json()
    assert b["taxa_poupanca"]["value"] is None
    assert b["taxa_poupanca"]["unavailable_reason"] == "sem_receita"
    assert b["aporte_sobre_trabalho"]["unavailable_reason"] == "sem_receita"
