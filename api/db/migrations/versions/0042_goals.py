"""goals + goal_assets — objetivos vinculados às caixinhas (Story 8.1)

Revision ID: 0042_goals
Revises: 0041_broker_cash_checks
Create Date: 2026-10-18

Donas `planning` (AD-11). `goals`: nome, valor-alvo e prazo; a reserva de emergência é um objetivo
fixo (`kind = 'reserva'`, uma só) cujo alvo = multiplicador × custos fixos (padrão 6) e horizonte
editável (padrão 12 meses). `goal_assets`: a decisão por ativo — `confirmed` (ligado ao objetivo) ou
`dismissed` (não é objetivo); sem linha, a caixinha é sugerida.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0042_goals"
down_revision: str | None = "0041_broker_cash_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
          id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          kind           text NOT NULL DEFAULT 'objetivo' CHECK (kind IN ('reserva', 'objetivo')),
          name           text NOT NULL CHECK (length(trim(name)) > 0),
          target         numeric(15, 2) CHECK (target IS NULL OR target > 0),
          deadline       date,
          multiplier     numeric(6, 2) CHECK (multiplier IS NULL OR multiplier > 0),
          horizon_months integer CHECK (horizon_months IS NULL OR horizon_months > 0),
          created_at     timestamptz NOT NULL DEFAULT now(),
          CHECK (kind = 'reserva' OR (target IS NOT NULL AND deadline IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS goals_one_reserve ON goals (kind) WHERE kind = 'reserva'"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS goal_assets (
          asset_id   uuid PRIMARY KEY REFERENCES assets(id),
          goal_id    uuid REFERENCES goals(id) ON DELETE CASCADE,
          status     text NOT NULL CHECK (status IN ('confirmed', 'dismissed')),
          decided_at timestamptz NOT NULL DEFAULT now(),
          CHECK ((status = 'confirmed') = (goal_id IS NOT NULL))
        )
        """
    )
    op.execute(
        "INSERT INTO goals (kind, name, multiplier, horizon_months) "
        "SELECT 'reserva', 'Reserva de emergência', 6, 12 "
        "WHERE NOT EXISTS (SELECT 1 FROM goals WHERE kind = 'reserva')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS goal_assets")
    op.execute("DROP TABLE IF EXISTS goals")
