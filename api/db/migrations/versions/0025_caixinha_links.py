"""asset_operations.transaction_id + protected — operações de caixinha ligadas à transação (AD-6,
Story 3.5)

Revision ID: 0025_caixinha_links
Revises: 0024_holder_balances
Create Date: 2026-10-18

- `transaction_id` (FK `ON DELETE RESTRICT`, único quando preenchido): a transação de onde a
  operação derivada veio. No histórico, pelo `external_id` (`caixinha:{símbolo}:{fitid}`) e, para
  transação sem FITID, pela chave de fallback `{data}:{valor}` de `caixinhas.py`.
- `protected`: curadoria que nenhuma derivação altera nem apaga — `caixinha-yield:*`, o resgate da
  Turbo reduzido por `register_caixinha_yields` (id citado na nota da op de juros) e o bucket
  Nubank-Encerradas.
Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0025_caixinha_links"
down_revision: str | None = "0024_holder_balances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE asset_operations ADD COLUMN IF NOT EXISTS transaction_id uuid "
        "REFERENCES transactions(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE asset_operations ADD COLUMN IF NOT EXISTS protected boolean "
        "NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_asset_operations_transaction "
        "ON asset_operations (transaction_id) WHERE transaction_id IS NOT NULL"
    )
    # pelo FITID
    op.execute(
        """
        UPDATE asset_operations o SET transaction_id = t.id
        FROM transactions t
        WHERE o.transaction_id IS NULL AND o.external_id LIKE 'caixinha:%'
          AND t.external_id
              = substr(o.external_id, length('caixinha:' || o.asset_symbol || ':') + 1)
        """
    )
    # fallback {data}:{valor} (transação sem FITID): a primeira ainda livre com a mesma data e valor
    op.execute(
        """
        UPDATE asset_operations o SET transaction_id = m.tx_id
        FROM (
          SELECT DISTINCT ON (o2.id) o2.id AS op_id, t.id AS tx_id
          FROM asset_operations o2
          JOIN transactions t ON t.external_id IS NULL
            AND t.date::text || ':' || to_char(abs(t.amount), 'FM9999999990.00')
                = substr(o2.external_id, length('caixinha:' || o2.asset_symbol || ':') + 1)
          WHERE o2.transaction_id IS NULL AND o2.external_id LIKE 'caixinha:%'
            AND NOT EXISTS (SELECT 1 FROM asset_operations x WHERE x.transaction_id = t.id)
          ORDER BY o2.id, t.created_at, t.id
        ) m
        WHERE o.id = m.op_id
        """
    )
    op.execute(
        """
        UPDATE asset_operations SET protected = true
        WHERE NOT protected AND (
          external_id LIKE 'caixinha-yield:%'
          OR asset_symbol = 'Nubank-Encerradas'
          OR id IN (
            SELECT substring(notes FROM 'resgate ([0-9a-f-]{36})')::uuid
            FROM asset_operations
            WHERE external_id = 'caixinha-yield:Nubank-Turbo'
              AND notes ~ 'resgate [0-9a-f-]{36}'
          )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_asset_operations_transaction")
    op.execute("ALTER TABLE asset_operations DROP COLUMN IF EXISTS protected")
    op.execute("ALTER TABLE asset_operations DROP COLUMN IF EXISTS transaction_id")
