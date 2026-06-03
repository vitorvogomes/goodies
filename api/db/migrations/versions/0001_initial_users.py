"""initial users table

Revision ID: 0001_initial_users
Revises:
Create Date: 2026-06-03

Cria a tabela `users` (id, email, password_hash, created_at) e habilita RLS.
gen_random_uuid() é nativo no Postgres 15 (sem extensão). Seed do admin: ver
api/scripts/seed_admin.py (não embute senha no repo — ADR-006 / security.md).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial_users"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email         text NOT NULL UNIQUE,
            password_hash text NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    # RLS habilitada (critério 00-03). App conecta como owner; políticas de acesso
    # refinadas entram quando houver multi-tenant — single-user no MVP.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users;")
