"""broker_cash_checks — "Saldo que vejo na corretora" (Story 7.7)

Revision ID: 0041_broker_cash_checks
Revises: 0040_debentures
Create Date: 2026-10-18

Dona `portfolio`. O saldo em caixa que o Vitor vê na corretora numa data, para comparar com o caixa
calculado (resíduo saiu + proventos − aplicado). Uma conferência por corretora e data; a nova da
mesma data substitui.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0041_broker_cash_checks"
down_revision: str | None = "0040_debentures"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_cash_checks (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          rail       text NOT NULL,
          as_of      date NOT NULL,
          balance    numeric(15, 2) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (rail, as_of)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS broker_cash_checks")
