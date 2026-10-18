"""month_plans — dívidas do mês, aporte planejado e travas da distribuição (Story 6.5)

Revision ID: 0034_month_plans
Revises: 0033_fixed_cost_payments
Create Date: 2026-10-18

Dona `planning` (AD-9: só decisão humana é gravada). Uma linha por mês, criada quando o Vitor
informa algo: `dividas` nulo = não informado (o orçamento usa o pré-preenchido das transações em
Dívidas); `aporte_planejado` nulo = não definido (`nao_definido`); `travas` da distribuição do
aporte (Épico 8). Num mês fechado é só leitura até reabrir (AD-8).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034_month_plans"
down_revision: str | None = "0033_fixed_cost_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS month_plans (
          month            date PRIMARY KEY CHECK (extract(day FROM month) = 1),
          dividas          numeric(15, 2) CHECK (dividas IS NULL OR dividas >= 0),
          aporte_planejado numeric(15, 2) CHECK (aporte_planejado IS NULL OR aporte_planejado >= 0),
          travas           jsonb NOT NULL DEFAULT '{}'::jsonb,
          updated_at       timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS month_plans")
