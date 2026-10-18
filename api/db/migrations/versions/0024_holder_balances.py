"""accounts.holder + account_balances — OFX completo (AD-5/AD-7, Story 3.4)

Revision ID: 0024_holder_balances
Revises: 0023_assets
Create Date: 2026-10-18

- `accounts.holder` ∈ {pf, mei}: a conferência de saldo é só da conta PF (a do MEI fica sempre
  zerada). Preenchido nas contas Nubank pelo nome cadastrado (`..._CNPJ`/MEI → mei; demais Nubank →
  pf), só onde ainda está nulo.
- `account_balances` (dono `ledger`): saldo informado pelo OFX (`LEDGERBAL`) por conta e data, com o
  `batch_id` do lote que o trouxe (desfazer o lote o remove).
Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024_holder_balances"
down_revision: str | None = "0023_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS holder text CHECK (holder IN ('pf', 'mei'))"
    )
    op.execute(
        """
        UPDATE accounts SET holder = CASE
            WHEN name ILIKE '%cnpj%' OR name ILIKE '%mei%' THEN 'mei' ELSE 'pf' END
        WHERE holder IS NULL AND name ILIKE 'nubank%' AND account_number IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS account_balances (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
          as_of      date NOT NULL,
          balance    numeric(15, 2) NOT NULL,
          batch_id   uuid REFERENCES import_batches(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (account_id, as_of)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_account_balances_batch ON account_balances (batch_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS account_balances")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS holder")
