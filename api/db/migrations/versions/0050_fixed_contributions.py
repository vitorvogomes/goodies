"""Aportes fixos do mês e o ativo PT sUSDai (pedido de 18/10/2026)

Revision ID: 0050_fixed_contributions
Revises: 0049_expected_incomes
Create Date: 2026-10-18

- `fixed_contributions` (dona `planning`): o valor que um objetivo (`goal:<id>`) ou um ativo
  (`asset:<id>`) recebe todo mês — a integralização da Flash, a caixinha de um objetivo. A
  Distribuição do aporte o trata como trava padrão de cada mês (a trava do próprio mês vence).
  Vigência como as metas: `valid_from` no dia 1, `valid_to` fecha a versão; uma ativa por chave.
- `assets` ganha o PT sUSDai (cripto, preço manual em US$): a posição DeFi passa a ter um
  `assets.id` e, com ele, meta por ativo. Idempotente pela `key`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0050_fixed_contributions"
down_revision: str | None = "0049_expected_incomes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fixed_contributions (
          id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          key         text NOT NULL CHECK (key ~ '^(goal|asset):[0-9a-f-]{36}$'),
          amount      numeric(15,2) NOT NULL CHECK (amount > 0),
          valid_from  date NOT NULL CHECK (EXTRACT(day FROM valid_from) = 1),
          valid_to    date CHECK (valid_to IS NULL OR valid_to >= valid_from),
          created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_fixed_contributions_active "
        "ON fixed_contributions (key) WHERE valid_to IS NULL"
    )
    op.execute(
        "INSERT INTO assets (key, name, class, price_ref, valuation) "
        "VALUES ('crypto:PT-SUSDAI', 'PT sUSDai', 'cripto', 'PT sUSDai', 'manual') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fixed_contributions")
    op.execute(
        "DELETE FROM assets a WHERE a.key = 'crypto:PT-SUSDAI' AND NOT EXISTS "
        "(SELECT 1 FROM portfolio_targets t WHERE t.asset_id = a.id)"
    )
