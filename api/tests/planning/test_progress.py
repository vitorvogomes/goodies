"""Story 8.7 — realizado, a caminho e pendente: golden dos mockups (out/2026, Aportes)."""

from __future__ import annotations

from decimal import Decimal

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
