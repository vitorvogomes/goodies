"""month_summary_totals: rentabilidade do mês nominal e real (Story 7.3)

Revision ID: 0037_summary_month_return
Revises: 0036_consolidado_price_day
Create Date: 2026-10-18

A rentabilidade do mês (XIRR do mês: valor investido no fim do mês anterior, fluxos do mês, valor no
fim) entra no resumo e no snapshot, nominal e real (descontado o IPCA do mês). Snapshots anteriores
ficam nulos (`fora_do_resumo`).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0037_summary_month_return"
down_revision: str | None = "0036_consolidado_price_day"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE month_summary_totals ADD COLUMN IF NOT EXISTS rentabilidade_mes numeric, "
        "ADD COLUMN IF NOT EXISTS rentabilidade_mes_real numeric"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE month_summary_totals DROP COLUMN IF EXISTS rentabilidade_mes, "
        "DROP COLUMN IF EXISTS rentabilidade_mes_real"
    )
