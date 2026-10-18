"""accounts.opening_balance — saldo de abertura da conferência encadeada (AD-7, Story 3.12)

Revision ID: 0027_opening_balance
Revises: 0026_broker_snapshots
Create Date: 2026-10-18

O saldo de abertura vem da âncora (o saldo informado mais antigo da conta PF): saldo informado − Σ
transações até a data da âncora. Gravado por `scripts.ops.ancorar_saldo`, que também guarda os
`LEDGERBAL` dos OFX mensais em `account_balances` (modo só-saldo, sem lote).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0027_opening_balance"
down_revision: str | None = "0026_broker_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS opening_balance numeric(15, 2)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS opening_balance_date date")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS opening_balance_date")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS opening_balance")
