"""categorize() como caminho único — fim da sincronia por nome (Story 2.5, AD-6)

Revision ID: 0020_categorize_chokepoint
Revises: 0019_category_rules
Create Date: 2026-10-18

Desde a Story 2.5 toda mudança de categoria de transação passa por `ledger.service.categorize()`.
O trigger transitório da 0018 deixa de sincronizar UPDATE por nome: fica só o INSERT sem
`category_id` (escritor legado ainda não migrado — o Hermes, desligado na v2.0), que resolve pelo
nome ou cai em "a classificar" pelo sinal. Custos fixos seguem com a sincronia até a Story 6.1.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_categorize_chokepoint"
down_revision: str | None = "0019_category_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_category_sync ON transactions")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_tx_category_fallback() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.category_id IS NULL THEN
            NEW.category_id := COALESCE(
              (SELECT id FROM categories WHERE name = NEW.category),
              (SELECT id FROM categories WHERE key = CASE
                 WHEN NEW.amount > 0 THEN 'sistema:entrada_a_classificar'
                 ELSE 'sistema:saida_a_classificar' END));
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_transactions_category_fallback BEFORE INSERT ON transactions "
        "FOR EACH ROW EXECUTE FUNCTION goodies_tx_category_fallback()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_category_fallback ON transactions")
    op.execute("DROP FUNCTION IF EXISTS goodies_tx_category_fallback()")
    op.execute(
        "CREATE TRIGGER trg_transactions_category_sync BEFORE INSERT OR UPDATE OF category "
        "ON transactions FOR EACH ROW EXECUTE FUNCTION goodies_sync_category_id()"
    )
