"""Receitas esperadas (Ajustes › Custos e receitas, pedido de 18/10/2026)

Revision ID: 0049_expected_incomes
Revises: 0048_fixed_cost_undo_many
Create Date: 2026-10-18

O planejamento das receitas do mês (salário, pagamentos a receber): nome, valor, dia, pagador e
vigência — como os custos fixos. Uma receita só de um mês tem `valid_to = valid_from`. O recebido
é derivado na leitura (entradas do trabalho do pagador no mês, `ledger/calc`); nada mais gravado.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0049_expected_incomes"
down_revision: str | None = "0048_fixed_cost_undo_many"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS expected_incomes (
          id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name        text NOT NULL CHECK (length(trim(name)) > 0),
          amount      numeric(15,2) NOT NULL CHECK (amount > 0),
          due_day     integer NOT NULL CHECK (due_day BETWEEN 1 AND 31),
          payer       text,
          valid_from  date NOT NULL CHECK (EXTRACT(day FROM valid_from) = 1),
          valid_to    date CHECK (valid_to IS NULL OR valid_to >= valid_from),
          created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS expected_incomes")
