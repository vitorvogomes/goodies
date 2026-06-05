"""transactions.notes + accounts.account_number

Revision ID: 0005_notes_account_number
Revises: 0004_categories
Create Date: 2026-06-04

Adendo 2. `transactions.notes`: observação livre por lançamento. `accounts.account_number`:
nº da conta (ex.: ACCTID do OFX "4288917-8") — habilita roteamento do import por
conta e a detecção de transferência interna (número na descrição). Índice único
parcial (vários NULL permitidos p/ contas manuais).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_notes_account_number"
down_revision: str | None = "0004_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN notes text;")
    op.execute("ALTER TABLE accounts ADD COLUMN account_number text;")
    op.execute(
        "CREATE UNIQUE INDEX idx_accounts_account_number "
        "ON accounts(account_number) WHERE account_number IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_accounts_account_number;")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS account_number;")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS notes;")
