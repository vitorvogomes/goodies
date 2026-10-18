"""Preço do consolidado B3 com a data dele (revisão da Story 7.1)

Revision ID: 0036_consolidado_price_day
Revises: 0035_summary_budget
Create Date: 2026-10-18

O import do consolidado gravava o preço com `fetched_at = now()`: o Carimbo de data e o histórico
(dia = `fetched_at`) chamavam de hoje um preço de 30/09. Agora `upsert_price(as_of=…)` grava a data
de referência; esta revisão corrige o que já existe: preço de fonte `b3` (só o consolidado escreve
essa fonte) datado depois do consolidado mais recente volta para a data dele, e a linha do
histórico com a data errada sai (a certa nasce pelo trigger).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036_consolidado_price_day"
down_revision: str | None = "0035_summary_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DAY = (
    "((SELECT max(ref_date) FROM broker_position_snapshots) + time '12:00') "
    "AT TIME ZONE 'America/Sao_Paulo'"
)


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM asset_price_history h USING asset_prices p
        WHERE h.ticker = p.ticker AND p.source = 'b3' AND h.source = 'b3'
          AND p.fetched_at > {_DAY}
          AND h.ref_date = (p.fetched_at AT TIME ZONE 'America/Sao_Paulo')::date
        """
    )
    op.execute(
        f"UPDATE asset_prices SET fetched_at = {_DAY} WHERE source = 'b3' AND fetched_at > {_DAY}"
    )


def downgrade() -> None:
    pass  # correção de dado: não há volta para a data errada
