"""ledger schema: accounts, transactions, fixed_costs + view monthly_summary

Revision ID: 0003_ledger
Revises: 0002_refresh_token_hash
Create Date: 2026-06-03

STORY-01-01. Schema de `02_Arquitetura.md` (sem ORM — SQL explícito). Acréscimo
aditivo: transactions.external_id (UUID FITID do extrato Nubank) com índice único
parcial, p/ idempotência do import (m1-ledger-nubank-source). RLS habilitada como
em users (single-user no MVP).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_ledger"
down_revision: str | None = "0002_refresh_token_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE accounts (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name       text NOT NULL,
            type       text NOT NULL,                 -- "bank", "broker", "crypto", "manual"
            currency   text NOT NULL DEFAULT 'BRL',
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE transactions (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id   uuid NOT NULL REFERENCES accounts(id),
            date         date NOT NULL,
            amount       numeric(15,2) NOT NULL,       -- positivo = receita, negativo = despesa
            category     text NOT NULL,
            description  text,
            is_recurring boolean NOT NULL DEFAULT false,
            external_id  text,                          -- FITID/Identificador Nubank (dedup import)
            created_at   timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_transactions_date ON transactions(date);")
    op.execute("CREATE INDEX idx_transactions_category ON transactions(category);")
    op.execute("CREATE INDEX idx_transactions_account ON transactions(account_id);")
    # external_id único quando presente; vários NULL permitidos (lançamentos manuais).
    op.execute(
        "CREATE UNIQUE INDEX idx_transactions_external_id "
        "ON transactions(external_id) WHERE external_id IS NOT NULL;"
    )
    op.execute(
        """
        CREATE TABLE fixed_costs (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name       text NOT NULL,
            amount     numeric(15,2) NOT NULL,
            due_day    integer NOT NULL,               -- dia do mês (1-31)
            category   text NOT NULL,
            is_active  boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # Resumo mensal de caixa (02_Arquitetura.md). savings_rate = net / receita * 100.
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

    # RLS habilitada (mesmo critério de users). App conecta como owner; políticas
    # multi-tenant entram se necessário — single-user no MVP.
    for table in ("accounts", "transactions", "fixed_costs"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS monthly_summary;")
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TABLE IF EXISTS fixed_costs;")
    op.execute("DROP TABLE IF EXISTS accounts;")
