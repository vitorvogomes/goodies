"""DeFi pelo saldo em US$ (v2.2)

Revision ID: 0051_defi_balance_anchors
Revises: 0050_fixed_contributions
Create Date: 2026-11-11

O saldo em dólar que o protocolo mostra numa data, a quantidade de tokens nessa data e, se
informado, o APY: o preço por token (saldo ÷ quantidade) rende por dia até o próximo saldo
(`wallet.defi_anchors`) — um depósito depois do saldo entra pelo mesmo preço. Substitui o preço
manual por token (calcular o preço à mão a cada rendimento). Nada muda nos dados existentes: o
preço manual segue até o 1º saldo informado.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0051_defi_balance_anchors"
down_revision: str | None = "0050_fixed_contributions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS defi_balance_anchors (
          defi_position_id uuid NOT NULL REFERENCES defi_positions(id) ON DELETE CASCADE,
          ref_date         date NOT NULL,
          value_usd        numeric(20,2) NOT NULL CHECK (value_usd >= 0),
          quantity         numeric(36,18) NOT NULL CHECK (quantity > 0),
          apy              numeric(9,4) CHECK (apy > -100 AND apy <= 1000),
          created_at       timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (defi_position_id, ref_date)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS defi_balance_anchors")
