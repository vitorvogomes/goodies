"""month_summary_totals.budget — o orçamento do mês congelado no fechamento (revisão do Épico 6)

Revision ID: 0035_summary_budget
Revises: 0034_month_plans
Create Date: 2026-10-18

Os termos da AD-7 continuam nas colunas (fonte de verdade do snapshot); `budget` guarda a Conta do
orçamento inteira (componentes, pagadores, consumido por grupo), montada na mesma passada, para a
tela de um mês fechado mostrar o congelado e não misturar o detalhe ao vivo com os totais.
Snapshots anteriores ficam nulos (a tela usa os totais e o resto sai `fora_do_resumo`).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035_summary_budget"
down_revision: str | None = "0034_month_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE month_summary_totals ADD COLUMN IF NOT EXISTS budget jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE month_summary_totals DROP COLUMN IF EXISTS budget")
