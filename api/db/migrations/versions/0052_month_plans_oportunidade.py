"""Oportunidade de mercado na distribuição do aporte (v2.2)

Revision ID: 0052_month_plans_oportunidade
Revises: 0051_defi_balance_anchors
Create Date: 2026-11-11

Liga/desliga, por mês, o ajuste da divisão entre os ativos de cada classe pela variação do preço
(`portfolio.opportunity`). Desligado por padrão: os meses existentes seguem com a distribuição de
sempre.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0052_month_plans_oportunidade"
down_revision: str | None = "0051_defi_balance_anchors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE month_plans "
        "ADD COLUMN IF NOT EXISTS oportunidade boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE month_plans DROP COLUMN IF EXISTS oportunidade")
