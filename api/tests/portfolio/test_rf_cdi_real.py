"""Story 7.4 — renda fixa pelo CDI real: cada aporte rende o %CDI do ativo sobre o CDI diário
publicado (benchmark_data) até a data; depois do último CDI não rende ("CDI até"); dia útil sem CDI
publicado usa o mais próximo e marca estimado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engines.portfolio.rf import cdi_value

D = Decimal
CDI = [(date(2025, 1, 6), D("0.05")), (date(2025, 1, 7), D("0.05")), (date(2025, 1, 8), D("0.05"))]


def _op(tipo: str, amount: str, d: date) -> dict[str, object]:
    return {"tipo": tipo, "quantidade": D(amount), "valor_unitario": D(1), "data_operacao": d}


def test_compounds_published_cdi_until_date() -> None:
    v = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 9), D(100), CDI)
    assert v.value == (D(1000) * D("1.0005") ** 3).quantize(D("0.01"))
    assert v.cdi_until == date(2025, 1, 8) and not v.estimated


def test_pct_cdi_and_redemption() -> None:
    ops = [_op("aporte", "1000", date(2025, 1, 6)), _op("resgate", "500", date(2025, 1, 8))]
    v = cdi_value(ops, date(2025, 1, 9), D(115), CDI)
    expected = D(1000) * (1 + D("0.05") * D("1.15") / 100) ** 3 - D(500) * (
        1 + D("0.05") * D("1.15") / 100
    )
    assert v.value == expected.quantize(D("0.01"))


def test_no_accrual_after_last_cdi_and_gap_estimated() -> None:
    late = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 20), D(100), CDI)
    assert late.value == (D(1000) * D("1.0005") ** 3).quantize(D("0.01"))  # CDI até 08/01
    gap = [CDI[0], (date(2025, 1, 10), D("0.05"))]  # 07, 08 e 09/01 (úteis) sem CDI publicado
    v = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 11), D(100), gap)
    assert v.estimated and v.value == (D(1000) * D("1.0005") ** 5).quantize(D("0.01"))


def test_without_any_cdi() -> None:
    v = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 9), D(100), [])
    assert v.value == D("1000.00") and v.cdi_until is None and v.estimated


@pytest.mark.parametrize("pct", [D(100), D("117.5")])
def test_money_is_cents(pct: Decimal) -> None:
    v = cdi_value([_op("aporte", "123.45", date(2025, 1, 6))], date(2025, 1, 9), pct, CDI)
    assert v.value == v.value.quantize(D("0.01"))


@pytest.mark.asyncio
async def test_valuation_job_and_positions_use_published_cdi(pool) -> None:
    """Integração: ativo de RF com %CDI cadastrado é valorado pelo CDI publicado no mês passado
    (cobertura "CDI real até"), o job `rf_cdi` grava o preço (fonte cdi, não manual) e Posições
    mostra "{x}% do CDI · CDI até dd/mm/aaaa"."""
    import uuid

    import main  # noqa: F401
    from engines.closing import service as closing
    from engines.common.owner import get_owner_id
    from engines.portfolio.valuation import valuation_as_of
    from workers.rf_cdi import run_rf_cdi

    symbol = f"RF-{uuid.uuid4().hex[:6]}"
    days = [date(2025, 3, d) for d in (3, 4, 5, 6, 7)]
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        asset = await conn.fetchval(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'Nubank', $2, 'Renda Fixa', "
            "'aporte', 1000, 1, '2025-03-03') RETURNING asset_id",
            owner,
            symbol,
        )
        await conn.execute(
            "UPDATE assets SET valuation = 'cdi', pct_cdi = 110 WHERE id = $1", asset
        )
        saved = await conn.fetch(
            "SELECT ref_date, value, source FROM benchmark_data WHERE series = 'CDI' "
            "AND ref_date = ANY($1::date[])",
            days,
        )
        await conn.execute(
            "DELETE FROM benchmark_data WHERE series = 'CDI' AND ref_date = ANY($1::date[])", days
        )
        for d in days:
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('CDI', $1, 0.05, 'teste')",
                d,
            )
        try:
            past = await valuation_as_of(conn, owner, date(2025, 3, 7))
            expected = (D(1000) * (1 + D("0.05") * D("1.10") / 100) ** 4).quantize(D("0.01"))
            assert past.by_asset[symbol] == expected  # 03, 04, 05 e 06/03 (o 07 é o próprio dia)
            assert past.coverage["RF"].startswith("CDI real até 06/03/2025")
            stats = await run_rf_cdi(pool, today=date(2025, 3, 7))
            assert stats["assets"] >= 1 and stats["updated"] >= 1
            price = await conn.fetchrow(
                "SELECT source, is_manual FROM asset_prices WHERE ticker = $1", symbol
            )
            assert (price["source"], price["is_manual"]) == ("cdi", False)
            report = await closing.positions(conn, "2025-03", "mes")
            row = next(a for c in report.classes for a in c.assets if a.symbol == symbol)
            assert row.nota is not None and row.nota.startswith("110% do CDI · CDI até ")
        finally:
            await conn.execute(
                "DELETE FROM benchmark_data WHERE series = 'CDI' AND ref_date = ANY($1::date[])",
                days,
            )
            for r in saved:
                await conn.execute(
                    "INSERT INTO benchmark_data (series, ref_date, value, source) "
                    "VALUES ('CDI', $1, $2, $3)",
                    r["ref_date"],
                    r["value"],
                    r["source"],
                )
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", symbol)
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", symbol)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", symbol)
            await conn.execute("DELETE FROM asset_aliases WHERE asset_id = $1", asset)
            await conn.execute("DELETE FROM assets WHERE id = $1", asset)


def test_estimated_share() -> None:
    gap = [CDI[0], (date(2025, 1, 10), D("0.05"))]
    v = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 11), D(100), gap)
    assert v.estimated_share == pytest.approx(3 / 5)
    full = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 9), D(100), CDI)
    assert full.estimated_share == 0


def test_pre_value_matches_flash_formula() -> None:
    """Story 7.6: 1.000 integralizados com fator 1,78% a.m. valem 1.000 × 1,0178^(dc/30)."""
    from engines.portfolio.rf import pre_value
    from engines.portfolio.rf_pre import valor_atual_pre

    ops = [_op("aporte", "1000", date(2025, 7, 1)), _op("aporte", "1000", date(2025, 8, 1))]
    got = pre_value(ops, date(2026, 10, 18), D("1.78"))
    legacy = valor_atual_pre(1000, 1.78, date(2025, 7, 1), date(2026, 10, 18)) + valor_atual_pre(
        1000, 1.78, date(2025, 8, 1), date(2026, 10, 18)
    )
    assert got == D(repr(legacy)).quantize(D("0.01"))


def test_holiday_between_published_days_does_not_accrue() -> None:
    """Revisão do Épico 7: feriado (dia útil sem CDI publicado entre dois publicados, até 2
    seguidos) não rende nem é estimado; lacuna maior segue estimada."""
    holiday = [CDI[0], (date(2025, 1, 8), D("0.05"))]  # 07/01 sem CDI: feriado
    v = cdi_value([_op("aporte", "1000", date(2025, 1, 6))], date(2025, 1, 9), D(100), holiday)
    assert v.value == (D(1000) * D("1.0005") ** 2).quantize(D("0.01"))
    assert not v.estimated and v.estimated_share == 0


def test_withdrawn_interest_leaves_the_balance() -> None:
    """Revisão do Épico 7: na caixinha, `juros` é o rendimento resgatado (o resgate foi reduzido
    dele) — sai do saldo como o resgate."""
    ops = [
        _op("aporte", "1000", date(2025, 1, 6)),
        _op("resgate", "400", date(2025, 1, 8)),
        _op("juros", "100", date(2025, 1, 8)),
    ]
    both = cdi_value(ops, date(2025, 1, 9), D(100), CDI)
    whole = cdi_value(
        [ops[0], _op("resgate", "500", date(2025, 1, 8))], date(2025, 1, 9), D(100), CDI
    )
    assert both.value == whole.value


def test_pre_value_stops_at_maturity() -> None:
    from engines.portfolio.rf import pre_value

    ops = [_op("aporte", "1000", date(2025, 7, 1))]
    at_maturity = pre_value(ops, date(2026, 7, 1), D("1.78"))
    assert pre_value(ops, date(2026, 10, 18), D("1.78"), date(2026, 7, 1)) == at_maturity


def test_anchor_replaces_history_before_it() -> None:
    """P28: o saldo informado (o que o app do banco mostra) numa data vira o ponto de partida:
    as operações até essa data saem, o saldo rende o %CDI dali em diante e as operações depois
    entram normalmente."""
    ops = [_op("aporte", "1000", date(2025, 1, 6)), _op("aporte", "200", date(2025, 1, 8))]
    anchor = [(date(2025, 1, 7), D("1500"))]
    at = cdi_value(ops, date(2025, 1, 7), D(100), CDI, anchors=anchor)
    assert at.value == D("1500.00")
    v = cdi_value(ops, date(2025, 1, 9), D(100), CDI, anchors=anchor)
    assert v.value == (D(1500) * D("1.0005") ** 2 + D(200) * D("1.0005")).quantize(D("0.01"))
    before = cdi_value(ops, date(2025, 1, 6), D(100), CDI, anchors=anchor)
    assert before.value == D("1000.00")  # antes da âncora, o histórico de sempre


def test_latest_anchor_wins() -> None:
    ops = [_op("aporte", "1000", date(2025, 1, 6))]
    anchors = [(date(2025, 1, 7), D("1500")), (date(2025, 1, 8), D("1600"))]
    v = cdi_value(ops, date(2025, 1, 9), D(100), CDI, anchors=anchors)
    assert v.value == (D(1600) * D("1.0005")).quantize(D("0.01"))
