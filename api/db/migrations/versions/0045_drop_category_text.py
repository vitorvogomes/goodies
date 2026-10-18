"""Fim do texto de categoria da v1 (Story 10.6 — FR36, AR18)

Revision ID: 0045_drop_category_text
Revises: 0044_metric_events
Create Date: 2026-10-18

Desde a 0018 a categoria de transação e de custo fixo é o `category_id` (a subcategoria); o texto
`transactions.category` / `fixed_costs.category` era só espelho para as telas v1, e
`categories.match_patterns` virou `category_rules` na 0019. As telas e rotas v1 saíram nesta
story, então as três colunas saem também:

- antes de apagar, confere o que se perderia: custo fixo sem `category_id` é resolvido pelo nome
  (e a revisão para se algum continuar sem); padrão de `match_patterns` sem regra equivalente em
  `category_rules` também para a revisão;
- o trigger de INSERT sem `category_id` (escritor que ainda não resolve a subcategoria) passa a
  cair só em "a classificar" pelo sinal; a sincronia por nome dos custos fixos sai.

Idempotente: cada passo confere a coluna antes. O downgrade recria as colunas a partir do
`category_id` e das regras.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0045_drop_category_text"
down_revision: str | None = "0044_metric_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has(table: str, column: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM information_schema.columns "
        f"WHERE table_name = '{table}' AND column_name = '{column}')"
    )


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF {_has("fixed_costs", "category")} THEN
            UPDATE fixed_costs f SET category_id = c.id
              FROM categories c WHERE f.category_id IS NULL AND c.name = f.category;
            IF EXISTS (SELECT 1 FROM fixed_costs WHERE category_id IS NULL) THEN
              RAISE EXCEPTION 'custo fixo sem subcategoria: resolva antes de apagar o texto';
            END IF;
          END IF;
          IF {_has("categories", "match_patterns")} THEN
            IF EXISTS (
              SELECT 1 FROM categories c, unnest(c.match_patterns) p
              WHERE NOT EXISTS (
                SELECT 1 FROM category_rules r WHERE lower(r.pattern) = lower(p)
              )
            ) THEN
              RAISE EXCEPTION 'padrão de categoria sem regra equivalente em category_rules';
            END IF;
          END IF;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_fixed_costs_category_sync ON fixed_costs")
    op.execute("DROP FUNCTION IF EXISTS goodies_sync_category_id()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_tx_category_fallback() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.category_id IS NULL THEN
            NEW.category_id := (SELECT id FROM categories WHERE key = CASE
              WHEN NEW.amount > 0 THEN 'sistema:entrada_a_classificar'
              ELSE 'sistema:saida_a_classificar' END);
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("ALTER TABLE fixed_costs ALTER COLUMN category_id SET NOT NULL")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS category")
    op.execute("ALTER TABLE fixed_costs DROP COLUMN IF EXISTS category")
    op.execute("ALTER TABLE categories DROP COLUMN IF EXISTS match_patterns")


def downgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category text")
    op.execute(
        "UPDATE transactions t SET category = c.name FROM categories c WHERE c.id = t.category_id"
    )
    op.execute("ALTER TABLE transactions ALTER COLUMN category SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category)"
    )
    op.execute("ALTER TABLE fixed_costs ADD COLUMN IF NOT EXISTS category text")
    op.execute(
        "UPDATE fixed_costs f SET category = c.name FROM categories c WHERE c.id = f.category_id"
    )
    op.execute("ALTER TABLE fixed_costs ALTER COLUMN category SET NOT NULL")
    op.execute("ALTER TABLE fixed_costs ALTER COLUMN category_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE categories ADD COLUMN IF NOT EXISTS match_patterns text[] NOT NULL "
        "DEFAULT '{}'"
    )
    op.execute(
        "UPDATE categories c SET match_patterns = r.patterns FROM ("
        "SELECT category_id, array_agg(pattern ORDER BY pattern) AS patterns "
        "FROM category_rules WHERE is_active GROUP BY category_id) r WHERE r.category_id = c.id"
    )
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
        """
        CREATE OR REPLACE FUNCTION goodies_sync_category_id() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' OR NEW.category IS DISTINCT FROM OLD.category THEN
            NEW.category_id := COALESCE(
              (SELECT id FROM categories WHERE name = NEW.category),
              CASE WHEN TG_OP = 'INSERT' THEN NEW.category_id END
            );
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_fixed_costs_category_sync BEFORE INSERT OR UPDATE OF category "
        "ON fixed_costs FOR EACH ROW EXECUTE FUNCTION goodies_sync_category_id()"
    )
