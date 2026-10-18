"""fixed_costs com vigência + fixed_cost_payments (decisões do casamento) — Story 6.1

Revision ID: 0033_fixed_cost_payments
Revises: 0032_summary_pct
Create Date: 2026-10-18

Dona `ledger` (AD-9: o casamento é derivado na leitura; só a decisão humana é gravada).
- `fixed_costs.valid_from`/`valid_to` (AD-14): os atuais entram com `valid_from` = jul/2024, para o
  `refechar` retroativo enxergá-los; desativado sem data ganha `valid_to` = o mês da criação.
- `fixed_cost_payments`: uma decisão por (custo, mês) — `confirmado`/`corrigido` (com a transação),
  `manual` (pago sem transação) e `desfeito` (aquela transação não é deste custo). A FK da transação
  é `ON DELETE CASCADE`: desfazer o lote (Story 3.14) leva a decisão junto.
Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033_fixed_cost_payments"
down_revision: str | None = "0032_summary_pct"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_UPGRADE = (
    "ALTER TABLE fixed_costs ADD COLUMN IF NOT EXISTS valid_from date",
    "ALTER TABLE fixed_costs ADD COLUMN IF NOT EXISTS valid_to date",
    "UPDATE fixed_costs SET valid_from = DATE '2024-07-01' WHERE valid_from IS NULL",
    "UPDATE fixed_costs SET valid_to = date_trunc('month', created_at)::date "
    "WHERE NOT is_active AND valid_to IS NULL",
    "ALTER TABLE fixed_costs ALTER COLUMN valid_from SET NOT NULL",
    "ALTER TABLE fixed_costs ALTER COLUMN valid_from "
    "SET DEFAULT date_trunc('month', now() AT TIME ZONE 'America/Sao_Paulo')::date",
    """
    DO $$ BEGIN
      ALTER TABLE fixed_costs ADD CONSTRAINT fixed_costs_valid_months CHECK (
        extract(day FROM valid_from) = 1
        AND (valid_to IS NULL OR (extract(day FROM valid_to) = 1 AND valid_to >= valid_from))
      );
    EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS fixed_cost_payments (
      id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      fixed_cost_id  uuid NOT NULL REFERENCES fixed_costs(id) ON DELETE CASCADE,
      month          date NOT NULL CHECK (extract(day FROM month) = 1),
      kind           text NOT NULL
                     CHECK (kind IN ('confirmado', 'corrigido', 'manual', 'desfeito')),
      transaction_id uuid REFERENCES transactions(id) ON DELETE CASCADE,
      created_at     timestamptz NOT NULL DEFAULT now(),
      CHECK ((kind = 'manual') = (transaction_id IS NULL)),
      UNIQUE (fixed_cost_id, month)
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_fixed_cost_payments_tx ON fixed_cost_payments "
    "(transaction_id) WHERE kind IN ('confirmado', 'corrigido')",
)


def upgrade() -> None:
    for statement in _UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fixed_cost_payments")
    op.execute("ALTER TABLE fixed_costs DROP CONSTRAINT IF EXISTS fixed_costs_valid_months")
    op.execute("ALTER TABLE fixed_costs DROP COLUMN IF EXISTS valid_to")
    op.execute("ALTER TABLE fixed_costs DROP COLUMN IF EXISTS valid_from")
