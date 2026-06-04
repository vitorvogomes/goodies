"""categories table + seed configurável

Revision ID: 0004_categories
Revises: 0003_ledger
Create Date: 2026-06-03

STORY-01-02. `categories` é a lista configurável (CRUD) que alimenta o dropdown
do front e a classificação do import Nubank. transactions.category permanece TEXT
livre (sem FK rígido — design de 02_Arquitetura.md). Seed = categorias da planilha
do Vitor + defaults BR; editável via CRUD.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_categories"
down_revision: str | None = "0003_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE categories (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name       text NOT NULL UNIQUE,
            kind       text NOT NULL CHECK (kind IN ('income','expense','investment','transfer')),
            is_active  boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY;")
    # Seed inicial (configurável). 'investment'/'transfer' separam o que NÃO é
    # consumo (Aplicação RDB, Pix interno) p/ a taxa de poupança não distorcer.
    op.execute(
        """
        INSERT INTO categories (name, kind) VALUES
          ('Flash Capital', 'income'),
          ('Betuel', 'income'),
          ('Salário', 'income'),
          ('Extra', 'income'),
          ('moradia', 'expense'),
          ('alimentação', 'expense'),
          ('transporte', 'expense'),
          ('saúde', 'expense'),
          ('lazer', 'expense'),
          ('educação', 'expense'),
          ('assinaturas', 'expense'),
          ('impostos', 'expense'),
          ('outros', 'expense'),
          ('Aplicação', 'investment'),
          ('Transferência interna', 'transfer')
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS categories;")
