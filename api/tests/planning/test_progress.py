"""Story 8.7 — realizado, a caminho e pendente: golden dos mockups (out/2026, Aportes)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from engines.planning.calc import aporte_progress

D = Decimal

SUGERIDO = {
    "goal:reserva": D(400),
    "goal:snow": D(900),
    "class:acoes_br": D(1250),
    "class:etfs": D(550),
    "class:fiis": D(800),
    "class:renda_fixa": D(200),
    "class:aposentadoria": D(300),
    "class:cripto": D(100),
}
REALIZADO = {
    "goal:reserva": D(400),
    "class:acoes_br": D(700),
    "class:etfs": D(550),
    "class:fiis": D(450),
    "class:renda_fixa": D(200),
}


def test_mockup_golden() -> None:
    p = aporte_progress(D(4500), D(2800), SUGERIDO, REALIZADO)
    assert (p.realizado, p.em_ativo, p.a_caminho, p.pendente) == (D(2800), D(2300), D(500), D(1700))
    line_pending = sum(pend for _, pend in p.lines.values())
    assert line_pending == D(2200) == p.pendente + p.a_caminho  # Σ pendente das linhas
    assert p.lines["class:fiis"] == (D(450), D(350)) and p.lines["goal:snow"] == (D(0), D(900))


def test_over_planned_and_next_month() -> None:
    over = aporte_progress(D(1000), D(1500), {"class:etfs": D(1000)}, {"class:etfs": D(1500)})
    assert over.pendente == D(0) and over.a_caminho == D(0)
    nothing = aporte_progress(D(0), D(0), {}, {})  # mês novo: nada carrega do anterior
    assert (nothing.pendente, nothing.realizado, nothing.lines) == (D(0), D(0), {})


@pytest.mark.asyncio
async def test_month_baseline_and_inflows_only(api, auth_headers, pool) -> None:
    """Revisão do Épico 8: a distribuição parte da posição antes do aporte do mês (fazer uma
    compra não muda a sugestão), e o realizado da linha só soma entradas (resgate é receita)."""
    import main  # noqa: F401
    from engines.common.dates import today_brt
    from engines.common.owner import get_owner_id
    from engines.portfolio.positions import month_contributions

    month = today_brt().replace(day=1)
    mes = f"{month:%Y-%m}"
    t = f"ZE{uuid.uuid4().hex[:2].upper()}11"
    url = "/api/v1/planning/distribution/preview"
    body = {"mes": mes, "planejado": "1000.00", "travas": {}}
    async with pool.acquire() as conn:
        owner = await get_owner_id(conn)
        await conn.execute(
            "INSERT INTO asset_prices (ticker, price_brl, source, is_manual) VALUES ($1, 10, "
            "'manual', true) ON CONFLICT (ticker) DO UPDATE SET price_brl = 10",
            t,
        )
    try:
        before = (await api.post(url, json=body, headers=auth_headers)).json()
        async with pool.acquire() as conn:
            for tipo, qty, day in (("compra", 30, month), ("venda", 5, month)):
                await conn.execute(
                    "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
                    "tipo, quantidade, valor_unitario, data_operacao) VALUES ($1, 'B3', $2, "
                    "'ETFs', $3, $4, 10, $5)",
                    owner,
                    t,
                    tipo,
                    qty,
                    day,
                )
            contributions, _ = await month_contributions(conn, owner, month)
            asset = str(
                await conn.fetchval(
                    "SELECT asset_id FROM asset_operations WHERE asset_symbol = $1", t
                )
            )
        after = (await api.post(url, json=body, headers=auth_headers)).json()
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", t)
            await conn.execute("DELETE FROM asset_prices WHERE ticker = $1", t)
            await conn.execute("DELETE FROM assets WHERE key = $1", f"b3:{t}")
    assert contributions[asset] == D(300)  # a venda não abate
    etf = lambda d: next(c for c in d["classes"] if c["cls"] == "etfs")  # noqa: E731
    # a sugestão do mês não muda com a compra (a venda tira 50 da base, que fica mais baixa)
    assert etf(after)["sugerido"] >= etf(before)["sugerido"]
    assert etf(after)["realizado"] == etf(before)["realizado"] + 300.0
