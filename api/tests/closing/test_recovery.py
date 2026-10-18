"""Story 5.8 — Assistente de recuperação: trilha do mês seguinte ao bloco fechado até o mês anterior
a hoje, derivada dos dados (pausar não perde nada); 4 passos — Importar (os arquivos cobrem o mês),
Revisar (sem pendentes no mês), Conferir (PF conferido/divergente), Fechar — com um único passo
atual; o próximo mês abre quando o atual fecha; tudo fechado → some."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import pytest
import pytest_asyncio

from engines.closing import service as closing

TODAY = date(2004, 4, 10)
BLOCK = [date(2004, 1, 1)]  # bloco retroativo: jan/2004 (a trilha começa em fev)


@pytest_asyncio.fixture
async def block(pool: Any) -> AsyncIterator[None]:
    async with pool.acquire() as conn:
        earliest = await conn.fetchval("SELECT min(month) FROM month_closes")
        assert earliest is None or earliest > date(2004, 12, 1), (
            "goodies_test com fechamento antigo"
        )
        for m in BLOCK:
            await conn.execute(
                "INSERT INTO month_closes (month, version, status, origin) "
                "VALUES ($1, 1, 'closed', 'retro')",
                m,
            )
            await conn.execute(
                "INSERT INTO month_summary_totals (month, version, as_of) VALUES ($1, 1, $2)",
                m,
                closing.month_end(m),
            )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM month_closes WHERE month < '2005-01-01'")


@pytest.mark.asyncio
async def test_recovery_trail(pool, block) -> None:
    import main  # noqa: F401

    async with pool.acquire() as conn:
        r = await closing.recovery(conn, TODAY, start=BLOCK[0])
        assert r.active
        assert r.base_until == date(2004, 1, 31)
        assert r.message == "A base vai até 31/01/2004. Recupere mês a mês até hoje."
        assert [m.month for m in r.months] == [date(2004, 2, 1), date(2004, 3, 1)]
        assert r.current == date(2004, 2, 1)
        steps = {s.key: s for s in r.steps}
        assert list(steps) == ["importar", "revisar", "conferir", "fechar"]
        assert sum(1 for s in r.steps if s.state == "atual") == 1
        assert steps["importar"].state == "atual"  # nenhum arquivo cobre 2004
        assert steps["revisar"].state == "feito"  # sem pendentes no mês
        assert steps["fechar"].state == "a_fazer"
        # o mesmo resultado em outra leitura: vem dos dados
        assert (await closing.recovery(conn, TODAY, start=BLOCK[0])) == r
        # fechar fev → a trilha avança para mar
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ('2004-02-01', 1, 'closed')"
        )
        await conn.execute(
            "INSERT INTO month_summary_totals (month, version, as_of) "
            "VALUES ('2004-02-01', 1, '2004-02-29')"
        )
        r2 = await closing.recovery(conn, TODAY, start=BLOCK[0])
        assert r2.current == date(2004, 3, 1)
        assert [(m.month, m.status) for m in r2.months] == [
            (date(2004, 2, 1), "fechado"),
            (date(2004, 3, 1), "aberto"),
        ]
        await conn.execute(
            "INSERT INTO month_closes (month, version, status) VALUES ('2004-03-01', 1, 'closed')"
        )
        await conn.execute(
            "INSERT INTO month_summary_totals (month, version, as_of) "
            "VALUES ('2004-03-01', 1, '2004-03-31')"
        )
        r3 = await closing.recovery(conn, TODAY, start=BLOCK[0])
    assert not r3.active and r3.months == [] and r3.steps == []


def test_steps_single_current() -> None:
    steps = closing.recovery_steps(
        "2026-06", imported=True, pending=3, balance="divergente", closed=False
    )
    assert [(s.key, s.state) for s in steps] == [
        ("importar", "feito"),
        ("revisar", "atual"),
        ("conferir", "a_fazer"),
        ("fechar", "a_fazer"),
    ]
    assert steps[2].detail == "divergente"
    assert steps[1].href == "/caixa/transacoes?periodo=2026-06&revisar=todas"
    done = closing.recovery_steps(
        "2026-06", imported=True, pending=0, balance="conferido", closed=False
    )
    assert [s.state for s in done] == ["feito", "feito", "feito", "atual"]


@pytest.mark.asyncio
async def test_recovery_route(api, auth_headers) -> None:
    r = await api.get("/api/v1/closing/recovery", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"active", "message", "months", "current", "steps"}


@pytest.mark.asyncio
async def test_close_without_wallet_history_estimates_crypto(pool) -> None:
    """Passo Fechar: sem histórico de carteira naquele fim de mês, o cripto entra como aplicado do
    bloco, com cobertura "estimada" (mesma regra do retroativo)."""
    import main  # noqa: F401

    async with pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM wallet_position_history WHERE ref_date <= '2004-02-29'"
        )
        summary = await closing.build_month_summary(conn, date(2004, 2, 1))
    assert summary.coverage["cripto"] == "estimada (aplicado do bloco)"
