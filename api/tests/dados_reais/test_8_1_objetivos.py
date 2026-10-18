"""Story 8.1 na base real: a revisão 0042 cria `goals`/`goal_assets` com a reserva de emergência
(6× os custos fixos, 12 meses) uma vez só — rodar de novo não duplica —, nenhum vínculo decidido
(o vínculo só vale confirmado) e as caixinhas vivas sugeridas (a Reserva → reserva de emergência;
as encerradas, não)."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from engines.planning import goals
from tests.dados_reais.conftest import restore_dados
from workers.dbops import alembic_upgrade

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_reserva_e_sugestoes_das_caixinhas() -> None:
    import main  # noqa: F401

    dsn = await restore_dados()
    try:
        await asyncio.to_thread(alembic_upgrade, dsn, "head")
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                "INSERT INTO goals (kind, name, multiplier, horizon_months) "
                "SELECT 'reserva', 'Reserva de emergência', 6, 12 "
                "WHERE NOT EXISTS (SELECT 1 FROM goals WHERE kind = 'reserva')"
            )  # o mesmo INSERT idempotente da revisão
            reserves = await conn.fetch("SELECT * FROM goals WHERE kind = 'reserva'")
            decided = await conn.fetchval("SELECT count(*) FROM goal_assets")
            out = await goals.list_goals(conn)
            costs = await goals.fixed_costs_total(conn, goals.today_brt().replace(day=1))
        finally:
            await conn.close()
    finally:
        await restore_dados()
    assert len(reserves) == 1 and (reserves[0]["multiplier"], reserves[0]["horizon_months"]) == (
        6,
        12,
    )
    assert decided == 0
    reserve = out.goals[0]
    assert reserve.kind == "reserva" and reserve.target == (costs * 6).quantize(reserve.target)
    labels = {s.label: s for s in out.suggestions}
    assert "Caixinha Reserva" in labels and labels["Caixinha Reserva"].goal_id == reserve.id
    assert {"Caixinha SnowTrip", "Caixinha Turbo"} <= set(labels)
    assert "Caixinha Encerradas" not in labels
