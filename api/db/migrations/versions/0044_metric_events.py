"""metric_events — registro da SM-1 (Story 10.5)

Revision ID: 0044_metric_events
Revises: 0043_targets_planning
Create Date: 2026-10-18

O comando `scripts.ops.metricas` grava o início da contagem da SM-1 (`sm1_inicio`) e cada abertura
da planilha "Rotina" (`planilha_aberta`, com o motivo), por escopo: `caixa` (a parcial do marco 2:
tarefas de caixa) ou `v2` (do marco 3 em diante). O resto das métricas só lê.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0044_metric_events"
down_revision: str | None = "0043_targets_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metric_events (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          kind       text NOT NULL CHECK (kind IN ('sm1_inicio', 'planilha_aberta')),
          scope      text NOT NULL DEFAULT 'v2' CHECK (scope IN ('caixa', 'v2')),
          day        date NOT NULL,
          note       text,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS metric_events")
