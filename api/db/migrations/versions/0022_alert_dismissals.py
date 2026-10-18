"""alert_dismissals — dispensas da Central de avisos (AD-10, Story 3.1)

Revision ID: 0022_alert_dismissals
Revises: 0021_reclassificacoes
Create Date: 2026-10-18

Os avisos são calculados na leitura; só a dispensa é gravada (key do aviso + fingerprint da condição
quando foi dispensado). Dona: engine `alerts`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022_alert_dismissals"
down_revision: str | None = "0021_reclassificacoes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_dismissals (
          key          text PRIMARY KEY,
          fingerprint  text NOT NULL,
          dismissed_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_dismissals")
