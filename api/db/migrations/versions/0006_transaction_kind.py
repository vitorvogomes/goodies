"""transactions.kind + categories.match_patterns + monthly_summary kind-aware

Revision ID: 0006_transaction_kind
Revises: 0005_notes_account_number
Create Date: 2026-06-04

Refator do ledger (m1): o import passa a GRAVAR todo movimento (inclusive
investimento/transferência), e o relatório decide o que é consumo via `kind`
(não mais pelo sinal do amount). Isso conserta o saldo fantasma (aplicações
saíam da conta mas não do saldo) e a taxa de poupança (depósitos a corretora
caíam como despesa).

- `transactions.kind` (income|expense|investment|transfer) — denormalizado, set
  no insert/import. Backfill por sinal+categoria (o caminho oficial é reset+reimport).
- `categories.match_patterns text[]` — classificação configurável dos destinos de
  investimento (substitui o `_INVESTMENT_KW` hardcoded). CNPJ de corretora é público.
- View `monthly_summary` kind-aware: total_expense = só consumo; savings_rate =
  (receita-despesa)/receita (B, gate jun/2026=55,48%); + total_invested e
  investment_rate (A). net_cashflow = receita-despesa (numerador da poupança),
  NÃO a variação de saldo (essa vive em cashflow.running_balance, SUM de tudo).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_transaction_kind"
down_revision: str | None = "0005_notes_account_number"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. coluna kind (default 'expense' permite ADD sem reescrita; CHECK espelha categories).
    op.execute(
        "ALTER TABLE transactions ADD COLUMN kind text NOT NULL DEFAULT 'expense' "
        "CHECK (kind IN ('income','expense','investment','transfer'));"
    )
    op.execute("CREATE INDEX idx_transactions_kind ON transactions(kind);")

    # Backfill de linhas pré-existentes (manuais). O reimport kind-aware é o caminho
    # oficial — o backfill por sinal NÃO conserta histórico mal-classificado.
    op.execute("UPDATE transactions SET kind = 'income' WHERE amount > 0;")
    op.execute("UPDATE transactions SET kind = 'expense' WHERE amount <= 0;")
    op.execute(
        "UPDATE transactions t SET kind = c.kind FROM categories c "
        "WHERE c.name = t.category AND c.kind IN ('investment','transfer');"
    )

    # 2. classificação configurável de destinos (keywords + CNPJs públicos).
    op.execute("ALTER TABLE categories ADD COLUMN match_patterns text[] NOT NULL DEFAULT '{}';")
    op.execute(
        """
        INSERT INTO categories (name, kind, match_patterns) VALUES
          ('Caixinha/RDB Nubank',      'investment',
             ARRAY['rdb','caixinha','aplicação','aplicacao','dinheiro guardado','resgate']),
          ('Renda Fixa Nubank',        'investment',
             ARRAY['tesouro','lci','lca','renda fixa']),
          ('Toro (B3)',                'investment',
             ARRAY['toro','corretora de titulos','ctvm','dtvm']),
          ('Binance',                  'investment',
             ARRAY['binance','gowd']),
          ('Liquid/DeFi',              'investment',
             ARRAY['plebank']),
          ('Flash Capital debêntures', 'investment',
             ARRAY['flash capital']),
          ('Flash Capital',            'income',
             ARRAY['securitizadora'])
        ON CONFLICT (name) DO UPDATE
          SET kind = EXCLUDED.kind, match_patterns = EXCLUDED.match_patterns;
        """
    )

    # 3. view kind-aware (DROP+CREATE: Postgres não troca colunas com CREATE OR REPLACE).
    op.execute("DROP VIEW IF EXISTS monthly_summary;")
    op.execute(
        """
        CREATE VIEW monthly_summary AS
        WITH agg AS (
          SELECT
            date_trunc('month', date) AS month,
            COALESCE(SUM(amount)  FILTER (WHERE kind = 'income'),     0) AS total_income,
            COALESCE(SUM(-amount) FILTER (WHERE kind = 'expense'),    0) AS total_expense,
            COALESCE(SUM(-amount) FILTER (WHERE kind = 'investment'), 0) AS total_invested
          FROM transactions
          GROUP BY date_trunc('month', date)
        )
        SELECT
          month,
          total_income,
          total_expense,
          total_income - total_expense AS net_cashflow,
          CASE WHEN total_income > 0
            THEN (total_income - total_expense) / total_income * 100 ELSE 0 END AS savings_rate,
          total_invested,
          CASE WHEN total_income > 0
            THEN total_invested / total_income * 100 ELSE 0 END AS investment_rate
        FROM agg
        ORDER BY month DESC;
        """
    )


def downgrade() -> None:
    # Restaura a view por sinal (0003) e remove as colunas aditivas.
    op.execute("DROP VIEW IF EXISTS monthly_summary;")
    op.execute(
        """
        CREATE VIEW monthly_summary AS
        SELECT
          date_trunc('month', date) AS month,
          SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS total_income,
          SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) AS total_expense,
          SUM(amount) AS net_cashflow,
          CASE WHEN SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) > 0
            THEN SUM(amount) / SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) * 100
            ELSE 0 END AS savings_rate
        FROM transactions
        GROUP BY date_trunc('month', date)
        ORDER BY month DESC;
        """
    )
    op.execute("ALTER TABLE categories DROP COLUMN IF EXISTS match_patterns;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_kind;")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS kind;")
