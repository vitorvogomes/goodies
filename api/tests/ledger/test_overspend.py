"""Story 6.4 — aviso de gasto acima da média: subcategoria de role `consumo` acima de 120% da média
dos 3 meses anteriores → "{Categoria} em R$ {valor}, {x}% acima da média de 3 meses." com Ver
transações filtradas pela categoria; investimento e caixinha nunca disparam."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.common.alerts import AlertContext
from engines.common.month_status import month_status
from engines.ledger import service as ledger


async def _spend(conn: Any, account: str, cat: Any, kind: str, values: dict[date, str]) -> None:
    for d, v in values.items():
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, "
            "description) VALUES ($1::uuid, $2, $3, $4, $5, $6)",
            account,
            d,
            Decimal(v),
            cat,
            kind,
            f"t {uuid.uuid4().hex[:6]}",
        )


@pytest.mark.asyncio
async def test_overspend_alert(pool, account) -> None:
    async with pool.acquire() as conn:
        consumo = await conn.fetchrow(
            "SELECT c.id, g.name || ' › ' || c.name AS label FROM categories c "
            "JOIN category_groups g ON g.id = c.group_id WHERE c.role = 'consumo' "
            "AND NOT g.is_system ORDER BY c.key LIMIT 1"
        )
        invest = await conn.fetchval(
            "SELECT id FROM categories WHERE role = 'investimento' ORDER BY key LIMIT 1"
        )
        history = {date(2096, 1, 10): "-100", date(2096, 2, 10): "-100", date(2096, 3, 10): "-100"}
        await _spend(conn, account, consumo["id"], "expense", {**history, date(2096, 4, 5): "-150"})
        await _spend(conn, account, invest, "investment", {**history, date(2096, 4, 5): "-900"})
        ctx = AlertContext(
            today=date(2096, 4, 20), periodo=date(2096, 4, 1), months=month_status(), owner_id="x"
        )
        alerts = await ledger.overspend_alerts(conn, ctx)
    mine = [a for a in alerts if a.key == f"gasto_acima_da_media:{consumo['id']}"]
    assert len(mine) == 1
    expected = f"{consumo['label']} em R$\u00a0150,00, 50% acima da média de 3 meses."
    assert mine[0].message == expected
    assert mine[0].action.label == "Ver transações"
    assert mine[0].action.params == {"periodo": "2096-04", "categoria": str(consumo["id"])}
    assert not [a for a in alerts if a.key == f"gasto_acima_da_media:{invest}"]
