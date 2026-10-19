"""Story 7.1 — Posições em dois níveis: classe → ativo com aplicado e valor atual no fim do mês e o
resultado do período da leitura (mês, tri, ano, início); preço desatualizado/ausente/manual
marcado; `closing.build_period_summary` soma os meses (fechado do snapshot, aberto ao vivo) e
nunca passa do período."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from engines.closing import service as closing
from engines.common.owner import get_owner_id
from engines.portfolio import calc
from tests.ledger.conftest import api as api
from tests.ledger.conftest import auth_headers as auth_headers

D = Decimal


def test_period_result_term() -> None:
    # fim 180, início 120, aportes do período 28, proventos 5 → 37
    assert calc.period_result(D(180), D(120), flows=D(28), income=D(5)) == D(37)


async def _seed(conn: Any, ticker: str) -> None:
    owner = await get_owner_id(conn)
    for tipo, qty, unit, d in (
        ("compra", 10, 10, date(2025, 1, 15)),
        ("compra", 2, 14, date(2025, 2, 10)),
        ("dividendo", 1, 5, date(2025, 2, 20)),
    ):
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, 'Ações Nacionais', "
            "$3, $4, $5, $6)",
            owner,
            ticker,
            tipo,
            qty,
            unit,
            d,
        )
    for d, price in ((date(2025, 1, 31), 12), (date(2025, 2, 28), 15)):
        await conn.execute(
            "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source) "
            "VALUES ($1, $2, $3, 'brapi')",
            ticker,
            d,
            price,
        )


async def _drop(conn: Any, ticker: str) -> None:
    await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", ticker)
    await conn.execute("DELETE FROM asset_price_history WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", ticker)
    await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{ticker}")


@pytest.mark.asyncio
async def test_positions_by_reading(pool: Any) -> None:
    import main  # noqa: F401

    t = f"ZQ{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        await _seed(conn, t)
        try:
            mes = await closing.positions(conn, "2025-02", "mes")
            inicio = await closing.positions(conn, "2025-02", "inicio")
            real = (
                await closing.real_since_start(conn, inicio.xirr_nominal.value, date(2025, 2, 1))
                if inicio.xirr_nominal.value is not None
                else None
            )
        finally:
            await _drop(conn, t)

    def asset(report: Any) -> Any:
        cls = next(c for c in report.classes if c.key == "acoes_br")
        return next(a for a in cls.assets if a.symbol == t)

    a = asset(mes)
    assert (a.aplicado, a.valor.value) == (D("128.00"), D("180.00"))
    assert a.resultado == D("37.00")  # 180 − 120 − 28 + 5
    b = asset(inicio)
    assert (b.aplicado, b.valor.value) == (D("128.00"), D("180.00"))  # mesmo fim de mês
    assert b.resultado == D("57.00")  # 180 − 128 + 5
    assert [m.month for m in mes.months] == [date(2025, 2, 1)]
    assert inicio.months[0].month == date(2024, 7, 1)
    assert inicio.months[-1].month == date(2025, 2, 1)  # nunca depois do período
    assert all(m.source in ("live", "snapshot") for m in inicio.months)
    if real is not None:  # revisão do Épico 7: a real desde o início é a do Painel
        assert inicio.xirr_real == real
    order = [c.key for c in mes.classes]
    assert order == ["acoes_br", "etfs", "fiis", "renda_fixa", "aposentadoria", "cripto"]
    crypto = mes.classes[-1]
    assert crypto.is_bucket and crypto.label == "Bloco cripto: quanto saiu × quanto vale"
    assert all(x.aplicado is None and x.resultado is None for x in crypto.assets)


@pytest.mark.asyncio
async def test_period_summary_sums_months(pool: Any) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        months = [date(2025, 1, 1), date(2025, 2, 1)]
        period = await closing.build_period_summary(conn, months)
        each = [await closing.month_summary(conn, m) for m in months]
    assert period.gastos == sum((s.gastos for s in each), D(0))
    assert period.receitas == sum((s.receitas for s in each), D(0))
    assert [(m.month, m.source) for m in period.months] == [(s.month, s.source) for s in each]
    # Story 9.1: as_of = o mais antigo, stale = OU, taxa dos componentes somados
    assert period.as_of == min(s.as_of for s in each)
    assert period.stale == any(s.income_stale or s.portfolio_stale for s in each)
    work = sum((s.trabalho for s in each), D(0))
    if work > 0:
        spent = sum((s.gastos - s.devolucoes for s in each), D(0))
        assert period.taxa_poupanca == ((work - spent) / work * 100).quantize(D("0.01"))


@pytest.mark.asyncio
async def test_price_flags_live(pool: Any) -> None:
    """Mês corrente: preço velho → "preço de dd/mm/aaaa" (stale); sem preço → sem_preco; manual."""
    import main  # noqa: F401
    from engines.common.dates import today_brt

    t_old, t_none, t_man = (f"Z{x}{uuid.uuid4().hex[:2].upper()}3" for x in "ABC")
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        for t in (t_old, t_none, t_man):
            await conn.execute(
                "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                "tipo, quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, "
                "'Ações Nacionais', 'compra', 1, 10, '2025-01-10')",
                owner,
                t,
            )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual, fetched_at) "
            "VALUES ($1, 11, 'brapi', false, now() - interval '10 days')",
            t_old,
        )
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) "
            "VALUES ($1, 12, 'manual', true)",
            t_man,
        )
        try:
            report = await closing.positions(conn, f"{today_brt():%Y-%m}", "mes")
        finally:
            for t in (t_old, t_none, t_man):
                await _drop(conn, t)
    rows = {a.symbol: a for c in report.classes for a in c.assets}
    assert rows[t_old].valor.stale and rows[t_old].valor.as_of is not None
    assert rows[t_none].valor.value is None
    assert rows[t_none].valor.unavailable_reason == "sem_preco"
    assert rows[t_man].manual is True
    # P9: a quantidade e o preço de cada ativo aparecem na linha (B3/Tesouro)
    assert (rows[t_man].quantidade, rows[t_man].preco) == (Decimal("1"), Decimal("12"))
    assert rows[t_none].preco is None and rows[t_none].quantidade == Decimal("1")


def test_period_xirr_and_real() -> None:
    """Story 7.3: XIRR do período (valor inicial como aporte, fluxos datados, valor final) e o real
    pelo IPCA efetivo do período."""
    start, end = date(2025, 1, 31), date(2025, 2, 28)
    r = calc.period_xirr(D(1000), start, [(date(2025, 2, 10), D(-100))], D(1110), end)
    assert r is not None and r > 0
    assert calc.period_xirr(D(1000), start, [], D(1000), end) == pytest.approx(0, abs=1e-6)
    assert calc.period_xirr(D(0), start, [], D(0), end) is None
    flat = calc.period_xirr(D(1000), start, [], D(1010), end)
    assert flat is not None
    factor = calc.ipca_factor([D("1.0")])  # 1% no período
    assert factor == D("1.01")
    real = calc.real_rate(flat, factor, (end - start).days)
    assert real == pytest.approx(0, abs=1e-3)  # rendeu o mesmo que a inflação
    assert calc.monthly_rate(0.12682503) == pytest.approx(0.01, rel=1e-6)


@pytest.mark.asyncio
async def test_period_return_nominal_and_real(pool: Any) -> None:
    """Story 7.3: XIRR do período por classe e consolidado; com o IPCA do mês, o real; sem ele,
    `aguardando_ipca` e a nominal normal. Por ativo, % a.m. (exceto RF e cripto)."""
    import main  # noqa: F401

    t = f"ZR{uuid.uuid4().hex[:2].upper()}3"
    feb = [date(2025, 2, 1)]
    async with pool.acquire() as conn:
        await _seed(conn, t)
        had = await conn.fetchval(
            "SELECT value FROM benchmark_data WHERE series = 'IPCA' AND ref_date = '2025-02-01'"
        )
        await conn.execute(
            "DELETE FROM benchmark_data WHERE series = 'IPCA' AND ref_date = '2025-02-01'"
        )
        try:
            waiting = await closing.period_return(conn, feb)
            # Posições (pedido de 18/10/2026): sem o IPCA do mês, estima com o último publicado
            jan_had = await conn.fetchval(
                "SELECT value FROM benchmark_data WHERE series = 'IPCA' AND ref_date = '2025-01-01'"
            )
            if jan_had is None:
                await conn.execute(
                    "INSERT INTO benchmark_data (series, ref_date, value, source) "
                    "VALUES ('IPCA', '2025-01-01', 0.16, 'teste')"
                )
            estimated = await closing.period_return(conn, feb, estimate_ipca=True)
            if jan_had is None:
                await conn.execute(
                    "DELETE FROM benchmark_data WHERE series = 'IPCA' AND ref_date = '2025-01-01'"
                )
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "VALUES ('IPCA', '2025-02-01', 1.31, 'teste')"
            )
            with_ipca = await closing.period_return(conn, feb)
            report = await closing.positions(conn, "2025-02", "mes")
        finally:
            await conn.execute(
                "DELETE FROM benchmark_data WHERE series = 'IPCA' AND ref_date = '2025-02-01'"
            )
            if had is not None:
                await conn.execute(
                    "INSERT INTO benchmark_data (series, ref_date, value, source) "
                    "VALUES ('IPCA', '2025-02-01', $1, 'bcb')",
                    had,
                )
            await _drop(conn, t)
    nominal, real = waiting.by_class["acoes_br"]
    assert nominal.value is not None and real.unavailable_reason == "aguardando_ipca"
    est_nominal, est_real = estimated.by_class["acoes_br"]
    assert est_nominal.value == nominal.value and est_real.value is not None
    assert estimated.ipca_ate is not None and estimated.ipca_ate < date(2025, 2, 28)
    nominal2, real2 = with_ipca.by_class["acoes_br"]
    assert nominal2.value == nominal.value and real2.value is not None
    assert real2.value < nominal2.value  # descontou a inflação
    acoes = next(c for c in report.classes if c.key == "acoes_br")
    asset = next(a for a in acoes.assets if a.symbol == t)
    assert asset.xirr_mensal is not None and asset.xirr_mensal > 0
    assert acoes.xirr_nominal.value is not None
    # pedido de 18/10/2026: a renda fixa também tem o % a.m. (o "rendimento ponderado pelo prazo"
    # da planilha); só o bloco cripto não (custo por ativo não existe)
    cripto = next(c for c in report.classes if c.key == "cripto")
    assert all(a.xirr_mensal is None for a in cripto.assets)
    # resultado total (valor − aplicado + proventos) ao lado do resultado do período
    assert asset.resultado_total is not None
    assert acoes.resultado_total == sum(
        (a.resultado_total for a in acoes.assets if a.resultado_total is not None), Decimal(0)
    )
    assert cripto.resultado_total == cripto.valor - (cripto.aplicado or Decimal(0))
    assert acoes.xirr_mensal is not None
    assert report.xirr_nominal.value is not None


@pytest.mark.asyncio
async def test_real_since_start_waits_for_ipca(pool: Any) -> None:
    async with pool.acquire() as conn:
        missing = await conn.fetchval(
            "SELECT count(*) FROM generate_series('2024-07-01'::date, '2025-01-01', '1 month') m "
            "WHERE NOT EXISTS (SELECT 1 FROM benchmark_data b WHERE b.series = 'IPCA' "
            "AND date_trunc('month', b.ref_date) = m)"
        )
        waiting = await closing.real_since_start(conn, D("12.00"), date(2025, 2, 1))
        none = await closing.real_since_start(conn, None, date(2025, 2, 1))
    assert none.unavailable_reason == "sem_preco"
    if missing:
        assert waiting.value is None and waiting.unavailable_reason == "aguardando_ipca"
    else:
        assert waiting.value is not None and waiting.value < D("12.00")


@pytest.mark.asyncio
async def test_positions_route_rejects_period_outside_base(api, auth_headers) -> None:
    """Revisão do Épico 7: antes da base (sem meses → 500) ou no futuro (fluxos do mês atual
    contados por mês futuro) → 422."""
    for periodo in ("2024-05", "2999-12"):
        r = await api.get(
            f"/api/v1/closing/positions?periodo={periodo}&leitura=tri", headers=auth_headers
        )
        assert r.status_code == 422 and r.json()["detail"]["error"] == "periodo_fora", r.text


@pytest.mark.asyncio
async def test_real_since_start_stamps_last_ipca_used(pool: Any) -> None:
    """Revisão do Épico 7: o Carimbo é o último mês de IPCA usado no cálculo (o fim do mês anterior
    ao período), não o último publicado."""
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(
                "INSERT INTO benchmark_data (series, ref_date, value, source) "
                "SELECT 'IPCA', m::date, 0.4, 'bcb' FROM generate_series('2024-07-01'::date, "
                "'2025-06-01', '1 month') m ON CONFLICT (series, ref_date) DO NOTHING"
            )
            real = await closing.real_since_start(conn, D("12.00"), date(2025, 2, 1))
        finally:
            await tx.rollback()
    assert real.value is not None and real.as_of == date(2025, 1, 31)


@pytest.mark.asyncio
async def test_sold_in_period_keeps_its_result(pool: Any) -> None:
    """Revisão do Épico 7: posição vendida dentro do período entra com valor 0 e o resultado do
    período (o XIRR da classe já contava os fluxos dela)."""
    import main  # noqa: F401

    t = f"ZV{uuid.uuid4().hex[:2].upper()}3"
    async with pool.acquire() as conn:
        await _seed(conn, t)
        await conn.execute(
            "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, tipo, "
            "quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, 'Ações Nacionais', "
            "'venda', 12, 16, '2025-02-25')",
            await get_owner_id(conn),
            t,
        )
        try:
            mes = await closing.positions(conn, "2025-02", "mes")
            mar = await closing.positions(conn, "2025-03", "mes")
        finally:
            await _drop(conn, t)

    def find(report: Any) -> Any:
        cls = next(c for c in report.classes if c.key == "acoes_br")
        return next((a for a in cls.assets if a.symbol == t), None)

    sold = find(mes)
    assert sold is not None and sold.valor.value == D(0) and sold.aplicado == D(0)
    assert sold.resultado == D("49.00")  # 0 − 120 − (28 − 192) + 5
    assert find(mar) is None  # vendida antes do período: fora


def test_estimated_start_class_is_left_out() -> None:
    """Story 8.3 (achado): sem histórico de preço cripto antes de 18/10/2026, o início do bloco é o
    aplicado (custo) e o fim é o valor de mercado — o retorno seria fabricado. A classe estimada no
    início sai do consolidado e fica "sem_preco"."""
    start_day, end_day = date(2026, 9, 30), date(2026, 10, 18)
    start = {"acoes_br": D(1000), "cripto": D(6000)}
    end = {"acoes_br": D(1010), "cripto": D(4600)}
    flows: dict[tuple[str, date], Decimal] = {}
    out = closing._returns(start, start_day, flows, end, end_day, None, None, frozenset({"cripto"}))
    only = closing._returns(
        {"acoes_br": D(1000)}, start_day, flows, {"acoes_br": D(1010)}, end_day, None, None
    )
    assert out.nominal == only.nominal
    assert out.by_class["cripto"][0].unavailable_reason == "sem_preco"
    assert out.by_class["acoes_br"][0] == only.by_class["acoes_br"][0]


@pytest.mark.asyncio
async def test_no_crypto_yet_is_not_estimated(pool: Any) -> None:
    """Revisão do Épico 8: antes de qualquer cripto, o bloco vale zero de verdade (não é a
    estimativa pelo aplicado que tira a classe do consolidado)."""
    from engines.portfolio.valuation import CRYPTO_ESTIMATED, valuation_as_of

    async with pool.acquire() as conn:
        v = await valuation_as_of(conn, await get_owner_id(conn), date(2001, 1, 31))
    assert v.coverage["cripto"] != CRYPTO_ESTIMATED and v.crypto_value == D(0)
