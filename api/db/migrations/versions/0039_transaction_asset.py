"""transactions.asset_id — o ativo de caixinha/CDB de cada transação (Story 7.5)

Revision ID: 0039_transaction_asset
Revises: 0038_rf_cdi
Create Date: 2026-10-18

Dona `ledger`; preenchida pelo resolver que `portfolio` registra (AD-1): a operação derivada ligada
pela transação (Story 3.5) ou, sem ela, a caixinha/CDB da descrição no trilho. O backfill do
histórico é o vínculo que já existe (asset_operations.transaction_id → asset_id): inclusive as
caixinhas encerradas no bucket `Nubank-Encerradas` (curadoria `protected`). Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0039_transaction_asset"
down_revision: str | None = "0038_rf_cdi"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS asset_id uuid REFERENCES assets(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_asset ON transactions (asset_id) "
        "WHERE asset_id IS NOT NULL"
    )
    op.execute(
        "UPDATE transactions t SET asset_id = o.asset_id FROM asset_operations o "
        "WHERE o.transaction_id = t.id AND o.asset_id IS NOT NULL "
        "AND t.asset_id IS DISTINCT FROM o.asset_id"
    )
    # caixinha encerrada: no trilho de caixinha sem operação ligada → o bucket (como hoje)
    op.execute(
        "UPDATE transactions t SET asset_id = a.id FROM categories c, assets a "
        "WHERE c.id = t.category_id AND c.key IN ('invest:caixinha_rdb', 'resgate:caixinha_rdb') "
        "AND a.price_ref = 'Nubank-Encerradas' AND t.asset_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM asset_operations o WHERE o.transaction_id = t.id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_asset")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS asset_id")
