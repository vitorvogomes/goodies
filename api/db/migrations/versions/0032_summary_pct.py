"""month_summary_totals: taxa_poupanca e rentabilidade sem limite de escala (revisão do Épico 5)

Revision ID: 0032_summary_pct
Revises: 0031_dirty_count
Create Date: 2026-10-18

`numeric(9,4)` estourava (NumericValueOutOfRange → o fechamento caía) num mês de receita do trabalho
pequena e gasto grande (ex.: R$ 5 de trabalho e R$ 6.000 de gastos = −119.900 %). O Pct continua
saindo com 2 casas (AD-4); a coluna só não limita a magnitude.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032_summary_pct"
down_revision: str | None = "0031_dirty_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE month_summary_totals ALTER COLUMN taxa_poupanca TYPE numeric, "
        "ALTER COLUMN rentabilidade TYPE numeric"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE month_summary_totals ALTER COLUMN taxa_poupanca TYPE numeric(9, 4), "
        "ALTER COLUMN rentabilidade TYPE numeric(9, 4)"
    )
