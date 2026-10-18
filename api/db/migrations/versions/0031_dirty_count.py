"""month_closes.dirty_count — contador de ajustes depois do fechamento (Story 5.6)

Revision ID: 0031_dirty_count
Revises: 0030_month_closes
Create Date: 2026-10-18

`mark_dirty` incrementa o contador da versão vigente; o aviso "Ajuste em {mês}" guarda o cálculo da
diferença em cache por mês e só refaz quando o contador muda. Fechar de novo nasce com 0.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031_dirty_count"
down_revision: str | None = "0030_month_closes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE month_closes ADD COLUMN IF NOT EXISTS dirty_count int NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE month_closes DROP COLUMN IF EXISTS dirty_count")
