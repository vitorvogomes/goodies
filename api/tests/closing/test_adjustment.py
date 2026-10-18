"""Story 5.6 — ajuste em mês fechado: o dado entra, o mês fica `dirty` (contador), o congelado não
muda; o aviso "Ajuste em {mês}…" traz a métrica de fluxo com a maior diferença (e mais {n}) e a ação
Reabrir mês; fechar de novo zera o `dirty`. Contrato: os quatro caminhos de escrita chamam
`mark_dirty`. Mês aberto depois do dia 15 do mês seguinte: "{Mês} segue aberto. Confira o saldo e
feche."."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import alerts as closing_alerts
from engines.closing import service as closing
from engines.common.alerts import AlertContext
from engines.common.month_status import month_status, register_month_status

MONTH = date(2025, 8, 1)


@pytest.fixture
async def clean(pool: Any, account: str):
    yield
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM month_closes WHERE month = ANY($1::date[])",
            [MONTH, date(2098, 12, 1)],
        )


async def _close(conn: Any, month: date) -> int:
    checks = await closing.run_checks(conn, month)
    if [c for c in checks if c.kind == "bloqueia"]:
        pytest.skip("mês de teste bloqueado no goodies_test")
    return (await closing.close_month(conn, month, [c.code for c in checks])).version


def _ctx(today: date) -> AlertContext:
    return AlertContext(
        today=today, periodo=today.replace(day=1), months=month_status(), owner_id="x"
    )


async def _expense(conn: Any, account: str, value: str) -> None:
    cat = await conn.fetchval(
        "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
        "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
    )
    await conn.execute(
        "INSERT INTO transactions (account_id, date, amount, category_id, kind, description, "
        "review_status, category_source) VALUES ($1::uuid, '2025-08-20', $2, $3, 'expense', "
        "$4, 'confirmed', 'manual')",
        account,
        Decimal(value),
        cat,
        f"ajuste {uuid.uuid4().hex[:6]}",
    )


@pytest.mark.asyncio
async def test_adjustment_flow(pool, account, clean) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        await _close(conn, MONTH)
        frozen = await closing.month_summary(conn, MONTH)
        await _expense(conn, account, "-50.00")
        await month_status().mark_dirty(conn, MONTH)
        await _expense(conn, account, "-25.00")
        await month_status().mark_dirty(conn, MONTH)
        row = await conn.fetchrow(
            "SELECT dirty, dirty_count FROM month_closes WHERE month = $1", MONTH
        )
        assert (row["dirty"], row["dirty_count"]) == (True, 2)
        assert await month_status().status(conn, MONTH) == "ajuste"
        assert (await closing.month_summary(conn, MONTH)).gastos == frozen.gastos
        found = [
            a
            for a in await closing_alerts.adjustment_alerts(conn, _ctx(date(2026, 1, 5)))
            if a.key == "ajuste:2025-08"
        ]
        assert len(found) == 1
        alert = found[0]
        assert alert.message.startswith(
            "Ajuste em ago/2025, já fechado. O resumo congelado não mudou. Se reabrir, gastos "
            "passa de R$\u00a0"
        )
        assert "e mais 1" in alert.message  # resultado do mês também muda
        assert alert.action.label == "Reabrir mês"
        assert alert.action.params == {"reabrir": "2025-08"}
        await closing.reopen_month(conn, MONTH)
        await _close(conn, MONTH)
        row = await conn.fetchrow(
            "SELECT dirty, dirty_count FROM month_closes WHERE month = $1 "
            "ORDER BY version DESC LIMIT 1",
            MONTH,
        )
        assert (row["dirty"], row["dirty_count"]) == (False, 0)
        assert not [
            a
            for a in await closing_alerts.adjustment_alerts(conn, _ctx(date(2026, 1, 5)))
            if a.key == "ajuste:2025-08"
        ]


@pytest.mark.asyncio
async def test_open_month_alert(pool, clean) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ('2098-12-01', 1, 'closed')"
        )
        await conn.execute(
            "INSERT INTO month_summary_totals (month, version, as_of) "
            "VALUES ('2098-12-01', 1, '2098-12-31')"
        )
        before = await closing_alerts.open_month_alerts(conn, _ctx(date(2099, 2, 15)))
        after = await closing_alerts.open_month_alerts(conn, _ctx(date(2099, 2, 16)))
    assert before == []
    assert [a.message for a in after] == ["Jan/2099 segue aberto. Confira o saldo e feche."]
    assert after[0].action.label == "Ir para Histórico"
    assert after[0].action.route == "/visao-geral/historico"


class _Spy:
    def __init__(self) -> None:
        self.months: list[date] = []

    async def status(self, conn: Any, month: date) -> str:
        return "aberto"

    async def is_closed(self, conn: Any, month: date) -> bool:
        return False

    async def mark_dirty(self, conn: Any, month: date) -> None:
        self.months.append(month)


@pytest.mark.asyncio
async def test_write_paths_mark_dirty(api, auth_headers, pool) -> None:
    """Contrato (AD-8): aplicar lote, desfazer lote, `categorize` e reaplicar regras chamam
    `mark_dirty` com os meses que tocam."""
    import main  # noqa: F401
    from engines.ledger import service as ledger
    from engines.ledger.models import ReapplyIn
    from tests.ingest.test_protocol import _ofx, _preview

    number = str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, 'bank', $2) "
            "RETURNING id",
            f"ofx-{number}",
            number,
        )
    original = month_status()
    spy = _Spy()
    register_month_status(spy)  # type: ignore[arg-type]
    try:
        body = (
            await _preview(
                api, auth_headers, [("c.ofx", _ofx(number, [uuid.uuid4().hex], "20990710"))]
            )
        ).json()
        r = await api.post(
            "/api/v1/ingest/confirm",
            json={"batch_id": body["batch_id"], "hash": body["hash"]},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert date(2099, 7, 1) in spy.months  # aplicar lote
        async with pool.acquire() as conn:
            tx = str(await conn.fetchval("SELECT id FROM transactions WHERE account_id = $1", acc))
            cat = str(
                await conn.fetchval(
                    "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                    "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
                )
            )
            spy.months.clear()
            await ledger.categorize(
                conn, [ledger.CategoryChange(tx, cat, "manual")], cause="inline_edit"
            )
            assert spy.months == [date(2099, 7, 1)]  # categorize
            word = "zqdirty" + uuid.uuid4().hex[:4].replace("0", "a")
            await conn.execute(
                "UPDATE transactions SET description = $2, category_source = 'rule' WHERE id = $1",
                tx,
                f"Loja {word}",
            )
            other = str(
                await conn.fetchval(
                    "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
                    "WHERE c.role = 'consumo' AND NOT g.is_system AND c.id <> $1 "
                    "ORDER BY c.key LIMIT 1",
                    cat,
                )
            )
            rule = await conn.fetchval(
                "INSERT INTO category_rules (pattern, direction, category_id) "
                "VALUES ($1, 'saida', $2) RETURNING id",
                word,
                other,
            )
            spy.months.clear()
            out = await ledger.reapply_rules(conn, ReapplyIn(de="2099-07", ate="2099-07"))
            await conn.execute("DELETE FROM category_rules WHERE id = $1", rule)
        assert out.changed >= 1 and date(2099, 7, 1) in spy.months  # reaplicar regras
        spy.months.clear()
        r = await api.post(f"/api/v1/ingest/batches/{body['batch_id']}/undo", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert date(2099, 7, 1) in spy.months  # desfazer lote
    finally:
        register_month_status(original)
        async with pool.acquire() as conn:
            from tests.ledger.conftest import _drop_account_data

            await _drop_account_data(conn, acc)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)


@pytest.mark.asyncio
async def test_undo_preview_closed_months(api, auth_headers, pool) -> None:
    import main  # noqa: F401
    from tests.ingest.test_protocol import _ofx, _preview

    number = str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number) VALUES ($1, 'bank', $2) "
            "RETURNING id",
            f"ofx-{number}",
            number,
        )
    original = month_status()

    class _Closed(_Spy):
        async def is_closed(self, conn: Any, month: date) -> bool:
            return month == date(2099, 8, 1)

    register_month_status(_Closed())  # type: ignore[arg-type]
    try:
        body = (
            await _preview(
                api, auth_headers, [("d.ofx", _ofx(number, [uuid.uuid4().hex], "20990810"))]
            )
        ).json()
        await api.post(
            "/api/v1/ingest/confirm",
            json={"batch_id": body["batch_id"], "hash": body["hash"]},
            headers=auth_headers,
        )
        pv = await api.post(
            f"/api/v1/ingest/batches/{body['batch_id']}/undo/preview", headers=auth_headers
        )
        assert pv.status_code == 200, pv.text
        assert pv.json()["closed_months"] == ["2099-08"]
        await api.post(f"/api/v1/ingest/batches/{body['batch_id']}/undo", headers=auth_headers)
    finally:
        register_month_status(original)
        async with pool.acquire() as conn:
            from tests.ledger.conftest import _drop_account_data

            await _drop_account_data(conn, acc)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)


@pytest.mark.asyncio
async def test_adjustment_cache_by_dirty_count(pool, account, clean) -> None:
    """O cálculo da diferença fica em cache por mês; só refaz quando o contador de `dirty` muda."""
    import main  # noqa: F401

    async with pool.acquire() as conn:
        await _close(conn, MONTH)
        await _expense(conn, account, "-10.00")
        await month_status().mark_dirty(conn, MONTH)
        ctx = _ctx(date(2026, 1, 5))

        def message(alerts):
            return next(a.message for a in alerts if a.key == "ajuste:2025-08")

        first = message(await closing_alerts.adjustment_alerts(conn, ctx))
        await _expense(conn, account, "-5.00")  # sem mark_dirty: o cache vale
        assert message(await closing_alerts.adjustment_alerts(conn, ctx)) == first
        await month_status().mark_dirty(conn, MONTH)
        assert message(await closing_alerts.adjustment_alerts(conn, ctx)) != first
