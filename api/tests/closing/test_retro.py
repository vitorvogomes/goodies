"""Story 5.7 — fechamento retroativo em bloco: cada mês por `build_month_summary` com origin retro,
confirmações automáticas "retroativo" (e "retroativo divergente · R$ x" no saldo PF divergente,
listado no fim), termos sem engine `fora_do_resumo`, aporte planejado/pendente `nao_definido`, mês
sem consolidado com "patrimônio não coberto"; consolidado não importado aborta (salvo
`--sem-consolidado`); fora do head aborta; rodar de novo não cria versão."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from scripts.ops import close_retro

MONTHS = [date(2001, 1, 1), date(2001, 2, 1), date(2001, 3, 1)]


@pytest_asyncio.fixture
async def clean(pool: Any) -> AsyncIterator[None]:
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM month_closes WHERE month = ANY($1::date[])", MONTHS)
        await conn.execute("DELETE FROM month_plans WHERE month = ANY($1::date[])", MONTHS)


@pytest_asyncio.fixture
async def pf_divergent(pool: Any) -> AsyncIterator[None]:
    """Conta PF com saldo informado em 31/01 e 28/02/2001 que não fecha (diferença R$ 30,00)."""
    async with pool.acquire() as conn:
        holders = await conn.fetch("SELECT id FROM accounts WHERE holder = 'pf'")
        await conn.execute("UPDATE accounts SET holder = NULL WHERE holder = 'pf'")
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type, account_number, holder) "
            "VALUES ($1, 'bank', $2, 'pf') RETURNING id",
            f"pf-{uuid.uuid4().hex[:6]}",
            str(uuid.uuid4().int)[:9],
        )
        for d, v in ((date(2001, 1, 31), "100.00"), (date(2001, 2, 28), "50.00")):
            await conn.execute(
                "INSERT INTO account_balances (account_id, as_of, balance) VALUES ($1, $2, $3)",
                acc,
                d,
                Decimal(v),
            )
        cat = await conn.fetchval(
            "SELECT id FROM categories WHERE key = 'sistema:saida_a_classificar'"
        )
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description, review_status) VALUES ($1, '2001-02-10', -20.00, 'x', $2, 'expense', "
            "'t', 'confirmed')",
            acc,
            cat,
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM account_balances WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
        await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
        await conn.execute(
            "UPDATE accounts SET holder = 'pf' WHERE id = ANY($1::uuid[])",
            [h["id"] for h in holders],
        )


@pytest.mark.asyncio
async def test_close_retro_block(pool, clean, pf_divergent, tmp_path: Path) -> None:
    import main  # noqa: F401

    said: list[str] = []
    async with pool.acquire() as conn:
        report = await close_retro.run(
            conn, MONTHS[0], MONTHS[-1], files_dir=tmp_path, echo=said.append
        )
        rows = await conn.fetch(
            "SELECT c.month, c.version, c.origin, c.confirmations, c.coverage, t.unavailable "
            "FROM month_closes c JOIN month_summary_totals t USING (month, version) "
            "WHERE c.month = ANY($1::date[]) ORDER BY c.month",
            MONTHS,
        )
        again = await close_retro.run(
            conn, MONTHS[0], MONTHS[-1], files_dir=tmp_path, echo=said.append
        )
        versions = await conn.fetchval(
            "SELECT count(*) FROM month_closes WHERE month = ANY($1::date[])", MONTHS
        )
    assert [r["month"] for r in rows] == MONTHS
    assert {(r["version"], r["origin"]) for r in rows} == {(1, "retro")}
    for r in rows:
        confirmations = json.loads(r["confirmations"])
        assert confirmations and all(c["reason"].startswith("retroativo") for c in confirmations)
        unavailable = json.loads(r["unavailable"])
        assert unavailable["pendente"] == "nao_definido"
        assert unavailable["aporte_planejado"] == "nao_definido"
        assert "realizado" not in unavailable  # Story 8.7: o investimento do mês, sempre conhecido
        assert json.loads(r["coverage"])["B3"] == "patrimônio não coberto"
    feb = json.loads(rows[1]["confirmations"])
    divergent = next(c for c in feb if c["code"] == "saldo_pf_divergente")
    assert divergent["kind"] == "confirma"
    assert divergent["reason"] == "retroativo divergente · R$\u00a030,00"
    assert report.divergent == [date(2001, 2, 1)]
    assert report.closed == MONTHS and again.closed == [] and versions == 3
    async with pool.acquire() as conn:  # refechar o divergente relê a confirmação com o valor
        from engines.closing import service as closing

        out = await closing.refechar(conn, date(2001, 2, 1), mode="completar")
    assert next(c for c in out.confirmations if c.code == "saldo_pf_divergente").amount == Decimal(
        "30.00"
    )
    assert any("fev/2001" in s and "divergente" in s for s in said)


def test_unimported_consolidado_aborts(tmp_path: Path) -> None:
    (tmp_path / "relatorio-consolidado-mensal-2001-fevereiro.xlsx").write_bytes(b"")
    (tmp_path / "relatorio-consolidado-anual-2000.xlsx").write_bytes(b"")
    missing = close_retro.unimported_consolidados(tmp_path, set(), MONTHS[0], MONTHS[-1])
    assert missing == [date(2001, 2, 1)]  # o anual de 2000 cai fora do intervalo
    assert (
        close_retro.unimported_consolidados(tmp_path, {date(2001, 2, 28)}, MONTHS[0], MONTHS[-1])
        == []
    )


@pytest.mark.asyncio
async def test_aborts_on_consolidado_and_head(pool, clean, tmp_path: Path) -> None:
    import main  # noqa: F401

    (tmp_path / "relatorio-consolidado-mensal-2001-fevereiro.xlsx").write_bytes(b"")
    async with pool.acquire() as conn:
        with pytest.raises(close_retro.RetroAborted, match="fev/2001"):
            await close_retro.run(conn, MONTHS[0], MONTHS[-1], files_dir=tmp_path)
        assert not await conn.fetchval(
            "SELECT count(*) FROM month_closes WHERE month = ANY($1::date[])", MONTHS
        )
        report = await close_retro.run(
            conn, MONTHS[0], MONTHS[0], files_dir=tmp_path, sem_consolidado=True
        )
    assert report.closed == [MONTHS[0]]
    with pytest.raises(close_retro.RetroAborted, match="head"):
        close_retro.ensure_head("0030_month_closes", "0031_dirty_count")
    close_retro.ensure_head("0031_dirty_count", "0031_dirty_count")


def test_scripts_register_engines() -> None:
    """Regressão: rodado fora da API, o comando precisa dos registros do `main` (sem eles o mês
    fechava sem nenhuma verificação)."""
    import subprocess
    import sys

    code = (
        "from engines.closing import checks\n"
        "from engines.common.month_status import month_status\n"
        "from scripts.ops import close_retro, refechar\n"
        "assert not checks._checks\n"
        "close_retro.register_engines(); refechar.register_engines()\n"
        "assert len(checks._checks) == 4, checks._checks\n"
        "assert type(month_status()).__name__ == 'ClosingMonthStatus'\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]


@pytest.mark.asyncio
async def test_retro_month_keeps_origin_and_reasons(pool, clean, tmp_path: Path) -> None:
    """Revisão do Épico 5: reabrir e fechar de novo um mês retroativo mantém `retro` (e as regras
    dele); `refechar` (completar e recalcular) não perde os motivos `nao_definido` nem a
    cobertura."""
    import main  # noqa: F401
    from engines.closing import service as closing

    month = MONTHS[0]
    async with pool.acquire() as conn:
        await close_retro.run(conn, month, month, files_dir=tmp_path)
        await closing.reopen_month(conn, month)
        checks = await closing.run_checks(conn, month)
        await closing.close_month(conn, month, [c.code for c in checks if c.kind == "confirma"])
        for mode in ("completar", "recalcular"):
            await closing.refechar(conn, month, mode=mode)
        rows = await conn.fetch(
            "SELECT c.version, c.origin, c.coverage, t.unavailable FROM month_closes c "
            "JOIN month_summary_totals t USING (month, version) WHERE c.month = $1 "
            "ORDER BY c.version",
            month,
        )
    assert [(r["version"], r["origin"]) for r in rows] == [
        (1, "retro"),
        (2, "retro"),
        (3, "retro"),
        (4, "retro"),
    ]
    for r in rows:
        unavailable = json.loads(r["unavailable"])
        assert unavailable["pendente"] == "nao_definido", r["version"]
        assert unavailable["aporte_planejado"] == "nao_definido", r["version"]
        assert "realizado" not in unavailable, r["version"]
        assert json.loads(r["coverage"])["B3"] == "patrimônio não coberto", r["version"]


@pytest.mark.asyncio
async def test_refechar_completes_budget_on_old_snapshot(pool, clean, tmp_path: Path) -> None:
    """Story 6.8: um mês retroativo fechado antes do orçamento (termos nulos `fora_do_resumo`)
    ganha, pelo `refechar --completar`, a versão seguinte com os termos do orçamento; o plano do mês
    vem de `ensure_month_plan(mode='retro')`: dívidas = Σ role `divida` não casada, aporte nulo."""
    import main  # noqa: F401
    from engines.closing import service as closing
    from engines.planning import service as planning

    month = MONTHS[2]
    budget_terms = (
        "consumido",
        "disponivel",
        "restante",
        "restante_sem_resgates",
        "consumo_financiado",
    )
    async with pool.acquire() as conn:
        await close_retro.run(conn, month, month, files_dir=tmp_path)
        sets = ", ".join(f"{t} = NULL" for t in budget_terms)
        reasons = json.dumps({t: "fora_do_resumo" for t in budget_terms})
        await conn.execute(
            f"UPDATE month_summary_totals SET {sets}, unavailable = unavailable || $2::jsonb "
            "WHERE month = $1",
            month,
            reasons,
        )
        await conn.execute("DELETE FROM month_plans WHERE month = $1", month)
        out = await closing.refechar(conn, month, mode="completar")
        row = await conn.fetchrow(
            "SELECT * FROM month_summary_totals WHERE month = $1 AND version = $2",
            month,
            out.version,
        )
        plan = await planning.month_plan(conn, month)
        prefill = (await planning.month_budget(conn, month)).dividas_prefill
        await conn.execute("DELETE FROM month_plans WHERE month = $1", month)
    unavailable = json.loads(row["unavailable"])
    for term in budget_terms:
        assert row[term] is not None and term not in unavailable, term
    assert unavailable["aporte_planejado"] == "nao_definido"
    assert plan.dividas == prefill and plan.aporte_planejado is None
