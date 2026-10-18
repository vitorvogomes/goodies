"""Caixinha de cada transação + Caixinha Ana Maria + Saldo separado (pendências P21 e conciliação)

Revision ID: 0046_caixinha_per_transaction
Revises: 0045_drop_category_text
Create Date: 2026-10-18

Desde 19/06/2026 o OFX do Nubank traz só "Aplicação RDB" / "Resgate RDB", sem o nome da caixinha:
a derivação pelo nome (`portfolio.caixinhas`) não acha a caixinha e o dinheiro some do patrimônio.

- `transaction_caixinha`: a caixinha escolhida para uma transação do trilho de caixinha; vence o
  casamento pela descrição.
- `caixinha:anamaria` (Nubank-AnaMaria, 100% do CDI), criada em out/2026.
- `transfer:saldo_separado`: o "Separar saldo" do Nubank (não rende; dinheiro dos custos fixos
  retirado ao longo do mês) é caixa da conta — transferência interna, fora de aporte e investimento.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0046_caixinha_per_transaction"
down_revision: str | None = "0045_drop_category_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS transaction_caixinha (
          transaction_id uuid PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
          asset_id       uuid NOT NULL REFERENCES assets(id),
          created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "INSERT INTO assets (key, name, class, price_ref, valuation, pct_cdi) VALUES "
        "('caixinha:anamaria', 'Nubank-AnaMaria', 'renda_fixa', 'Nubank-AnaMaria', 'cdi', 100) "
        "ON CONFLICT (key) DO UPDATE SET valuation = 'cdi', pct_cdi = 100"
    )
    op.execute(
        "INSERT INTO categories (name, kind, group_id, role, key) "
        "SELECT 'Saldo separado', 'transfer', g.id, 'transferencia', 'transfer:saldo_separado' "
        "FROM category_groups g WHERE g.key = 'transferencias' "
        "AND NOT EXISTS (SELECT 1 FROM categories WHERE key = 'transfer:saldo_separado')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transaction_caixinha")
    op.execute(
        "DELETE FROM categories c WHERE c.key = 'transfer:saldo_separado' "
        "AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.category_id = c.id)"
    )
    op.execute(
        "DELETE FROM assets a WHERE a.key = 'caixinha:anamaria' "
        "AND NOT EXISTS (SELECT 1 FROM asset_operations o WHERE o.asset_id = a.id)"
    )
