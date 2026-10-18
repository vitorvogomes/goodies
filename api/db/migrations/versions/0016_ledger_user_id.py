"""ledger com user_id — 1ª revisão de dado da v2 (AD-16 passo 1, Story 2.2)

Revision ID: 0016_ledger_user_id
Revises: 0015_job_runs
Create Date: 2026-10-18

As tabelas do ledger (`accounts`, `transactions`, `categories`, `fixed_costs`) ganham `user_id`
NOT NULL, preenchido com o dono único (o 1º usuário, como `common.owner.get_owner_id`). O DEFAULT
é a função `goodies_owner_id()`, para os caminhos de escrita v1 que ainda não passam o dono
continuarem gravando certo até serem migrados. Idempotente: rodar de novo não muda nada.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_ledger_user_id"
down_revision: str | None = "0015_job_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("accounts", "transactions", "categories", "fixed_costs")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_owner_id() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT id FROM users ORDER BY created_at, id LIMIT 1 $$;
        """
    )
    # Sem usuário e com linhas no ledger não há dono para atribuir: aborta em vez de inventar.
    op.execute(
        """
        DO $$
        BEGIN
          IF goodies_owner_id() IS NULL AND (
               EXISTS (SELECT 1 FROM accounts) OR EXISTS (SELECT 1 FROM transactions)
            OR EXISTS (SELECT 1 FROM categories) OR EXISTS (SELECT 1 FROM fixed_costs)) THEN
            RAISE EXCEPTION 'ledger com dados e nenhum usuário: rode scripts.ops.seed_admin antes';
          END IF;
        END $$;
        """
    )
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id)"
        )
        op.execute(f"UPDATE {table} SET user_id = goodies_owner_id() WHERE user_id IS NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET DEFAULT goodies_owner_id()")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")
        op.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user ON {table}(user_id)")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_user")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS user_id")
    op.execute("DROP FUNCTION IF EXISTS goodies_owner_id()")
