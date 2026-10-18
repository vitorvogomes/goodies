"""Story 7.7 — caixa em corretora × a caminho: do resíduo da corretora (saiu + proventos −
aplicado), as transferências depois do "atualizado até" do relatório ficam a caminho (fora do
patrimônio); o resto é caixa em corretora (no patrimônio)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engines.portfolio.calc import broker_split
from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers

D = Decimal


def test_covered_residual_is_broker_cash() -> None:
    cash, transit = broker_split(D("300"), [(date(2026, 9, 10), D("1000"))], date(2026, 9, 30))
    assert (cash, transit) == (D("300"), D("0"))


def test_transfer_after_report_is_on_the_way() -> None:
    transfers = [(date(2026, 9, 10), D("1000")), (date(2026, 10, 5), D("700"))]
    cash, transit = broker_split(D("900"), transfers, date(2026, 9, 30))
    assert (cash, transit) == (D("200"), D("700"))


def test_on_the_way_never_exceeds_residual() -> None:
    cash, transit = broker_split(D("400"), [(date(2026, 10, 5), D("700"))], date(2026, 9, 30))
    assert (cash, transit) == (D("0"), D("400"))


def test_no_residual() -> None:
    assert broker_split(D("0.50"), [(date(2026, 10, 5), D("700"))], date(2026, 9, 30)) == (
        D("0"),
        D("0"),
    )
    assert broker_split(D("-20"), [], None) == (D("0"), D("0"))


@pytest.mark.asyncio
async def test_cards_check_and_divergence(api, auth_headers, pool) -> None:
    """Cartões de corretora, "Saldo que vejo na corretora" e o aviso de caixa divergente."""
    import main  # noqa: F401
    from engines.common.alerts import AlertContext
    from engines.common.dates import today_brt
    from engines.common.month_status import month_status
    from engines.common.owner import get_owner_id
    from engines.portfolio.brokers import broker_alerts

    cards = (await api.get("/api/v1/portfolio/brokers", headers=auth_headers)).json()
    assert [c["name"] for c in cards] == ["B3", "Tesouro Direto", "Renda Fixa Nubank", "Flash"]
    flash = next(c for c in cards if c["name"] == "Flash")
    day = date(2001, 1, 2)  # conferência antiga: vale a mais recente até hoje
    try:
        informed = Decimal(str(flash["caixa"])) + D("5.00")
        r = await api.post(
            "/api/v1/portfolio/brokers/checks",
            json={"rail": flash["rail"], "as_of": day.isoformat(), "balance": str(informed)},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        after = next(c for c in r.json() if c["name"] == "Flash")
        assert after["divergent"] is True and after["informed_at"] == day.isoformat()
        async with pool.acquire() as conn:
            ctx = AlertContext(
                today=today_brt(),
                periodo=today_brt().replace(day=1),
                months=month_status(),
                owner_id=await get_owner_id(conn),
            )
            alerts = {a.key: a for a in await broker_alerts(conn, ctx)}
        alert = alerts[f"caixa_divergente:{flash['rail']}"]
        assert alert.message.startswith("Caixa na Flash: calculado R$")
        bad = await api.post(
            "/api/v1/portfolio/brokers/checks",
            json={"rail": "Outra", "as_of": day.isoformat(), "balance": "1.00"},
            headers=auth_headers,
        )
        assert bad.status_code == 422
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM broker_cash_checks WHERE as_of = $1", day)


def test_ad13_quantity_tolerances() -> None:
    """Story 7.9 — tolerâncias da AD-13 em portfolio/calc (por quantidade)."""
    from engines.portfolio.calc import quantity_status

    assert quantity_status("acoes_br", D("10"), D("10")) == "conferido"
    assert quantity_status("fiis", D("10"), D("9")) == "divergente"
    assert quantity_status("etfs", D("1"), D("1.0001")) == "divergente"  # exata
    assert quantity_status("aposentadoria", D("1.23"), D("1.24")) == "conferido"  # 0,01 título
    assert quantity_status("aposentadoria", D("1.23"), D("1.25")) == "divergente"
    assert quantity_status("cripto", D("0.5"), D("0.5000001")) == "divergente"
    assert quantity_status("renda_fixa", D("1000"), None) == "valor calculado"
