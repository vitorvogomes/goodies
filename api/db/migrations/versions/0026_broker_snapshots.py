"""broker_position_snapshots — posição informada pelo consolidado da B3 (AD-5/AD-13, Story 3.8)

Revision ID: 0026_broker_snapshots
Revises: 0025_caixinha_links
Create Date: 2026-10-18

Dona `portfolio`. Uma linha por (data de referência, ativo): quantidade e valor informados pelo
consolidado (mensal = fim do mês; anual = 31/12), com o `batch_id` do lote que a trouxe. Base da
conciliação e do fechamento; nada no histórico é derivado dela.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026_broker_snapshots"
down_revision: str | None = "0025_caixinha_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_position_snapshots (
          id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          ref_date       date NOT NULL,
          asset_id       uuid NOT NULL REFERENCES assets(id),
          quantity       numeric(20, 8) NOT NULL,
          reported_value numeric(15, 2),
          batch_id       uuid REFERENCES import_batches(id) ON DELETE RESTRICT,
          created_at     timestamptz NOT NULL DEFAULT now(),
          UNIQUE (ref_date, asset_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_broker_snapshots_batch "
        "ON broker_position_snapshots (batch_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS broker_position_snapshots")
