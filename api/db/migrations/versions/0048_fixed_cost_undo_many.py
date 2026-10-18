"""Custo fixo: várias transações desfeitas no mesmo mês (pendência P13)

Revision ID: 0048_fixed_cost_undo_many
Revises: 0047_rf_balance_anchors
Create Date: 2026-10-18

Com uma decisão por custo e mês, desfazer a segunda candidata trocava a primeira desfeita por ela,
e a primeira voltava sozinha (Cemig de mai/2025). Agora: uma decisão de pagamento (confirmado,
corrigido ou manual) por custo e mês, e quantas transações desfeitas forem preciso.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0048_fixed_cost_undo_many"
down_revision: str | None = "0047_rf_balance_anchors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fixed_cost_payments "
        "DROP CONSTRAINT IF EXISTS fixed_cost_payments_fixed_cost_id_month_key"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_fixed_cost_payments_decision "
        "ON fixed_cost_payments (fixed_cost_id, month) WHERE kind <> 'desfeito'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_fixed_cost_payments_undone "
        "ON fixed_cost_payments (fixed_cost_id, month, transaction_id) WHERE kind = 'desfeito'"
    )


def downgrade() -> None:
    # volta a uma decisão por custo e mês: fica a mais recente
    op.execute(
        "DELETE FROM fixed_cost_payments p USING fixed_cost_payments q "
        "WHERE p.fixed_cost_id = q.fixed_cost_id AND p.month = q.month "
        "AND (p.created_at, p.id) < (q.created_at, q.id)"
    )
    op.execute("DROP INDEX IF EXISTS ux_fixed_cost_payments_undone")
    op.execute("DROP INDEX IF EXISTS ux_fixed_cost_payments_decision")
    op.execute(
        "ALTER TABLE fixed_cost_payments ADD CONSTRAINT "
        "fixed_cost_payments_fixed_cost_id_month_key UNIQUE (fixed_cost_id, month)"
    )
