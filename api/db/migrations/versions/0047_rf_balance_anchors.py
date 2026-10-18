"""Saldo informado da renda fixa pelo CDI (pendência P28)

Revision ID: 0047_rf_balance_anchors
Revises: 0046_caixinha_per_transaction
Create Date: 2026-10-18

O saldo que o app do banco mostra numa data (ou cotas × valor da cota, no fundo da Reserva) vira o
ponto de partida da valoração pelo CDI: as operações até essa data saem e o saldo rende o %CDI do
ativo dali em diante (`portfolio.rf.cdi_value`). Corrige a deriva de meses entre o CDI calculado e o
que o banco credita.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0047_rf_balance_anchors"
down_revision: str | None = "0046_caixinha_per_transaction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rf_balance_anchors (
          asset_id    uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
          ref_date    date NOT NULL,
          value       numeric(14,2) NOT NULL CHECK (value >= 0),
          quotas      numeric(20,8),
          quota_value numeric(20,8),
          created_at  timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (asset_id, ref_date),
          CHECK ((quotas IS NULL) = (quota_value IS NULL))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rf_balance_anchors")
