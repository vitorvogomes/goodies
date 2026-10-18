"""job_runs.last_success_at — último sucesso de cada job (AD-10, Story 4.3)

Revision ID: 0028_job_last_success
Revises: 0027_opening_balance
Create Date: 2026-10-18

O heartbeat (`last_run`, `ok`) diz quando o job rodou; o aviso de worker atrasado precisa de quando
ele deu certo. Execução "ok" mas parcial (fonte falhando por dentro do fail-soft) não conta como
sucesso. No histórico, vale `last_run` dos que terminaram ok.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028_job_last_success"
down_revision: str | None = "0027_opening_balance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS last_success_at timestamptz")
    op.execute(
        "UPDATE job_runs SET last_success_at = last_run WHERE ok AND last_success_at IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE job_runs DROP COLUMN IF EXISTS last_success_at")
