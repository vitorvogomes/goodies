"""portfolio_targets passa a ser de `planning` — banda, piso e vigência (Story 8.2)

Revision ID: 0043_targets_planning
Revises: 0042_goals
Create Date: 2026-10-18

AD-11: metas por classe (`asset_id` nulo) e por ativo, com banda (p.p.), piso (R$) e vigência
(`valid_from` … `valid_to`; salvar as metas grava uma versão a partir do mês). As metas atuais são
mantidas (mesmo % por classe), vigentes desde jul/2024, com banda de 5 p.p. e piso 0 (P22). A
tabela vazia recebe as metas de `portfolio/targets.py` (o seed que sai). Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0043_targets_planning"
down_revision: str | None = "0042_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULTS = (
    ("Ações Nacionais", "10.00"),
    ("Aposentadoria", "12.50"),
    ("Cripto", "5.00"),
    ("ETFs", "12.50"),
    ("FIIs", "10.00"),
    ("Renda Fixa", "50.00"),
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE portfolio_targets "
        "DROP CONSTRAINT IF EXISTS portfolio_targets_user_id_category_key"
    )
    op.execute(
        "ALTER TABLE portfolio_targets DROP CONSTRAINT IF EXISTS portfolio_targets_target_pct_check"
    )
    op.execute(
        "ALTER TABLE portfolio_targets ADD CONSTRAINT portfolio_targets_target_pct_check "
        "CHECK (target_pct >= 0 AND target_pct <= 100)"
    )
    op.execute(
        "ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS band_pp numeric(5, 2) "
        "NOT NULL DEFAULT 5 CHECK (band_pp >= 0)"
    )
    op.execute(
        "ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS floor numeric(15, 2) "
        "NOT NULL DEFAULT 0 CHECK (floor >= 0)"
    )
    op.execute(
        "ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS valid_from date "
        "NOT NULL DEFAULT '2024-07-01'"
    )
    op.execute("ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS valid_to date")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS portfolio_targets_version ON portfolio_targets "
        "(user_id, category, coalesce(asset_id, '00000000-0000-0000-0000-000000000000'::uuid), "
        "valid_from)"
    )
    values = ", ".join(f"('{label}', {pct})" for label, pct in _DEFAULTS)
    op.execute(
        "INSERT INTO portfolio_targets (user_id, category, target_pct) "
        f"SELECT u.id, d.category, d.pct FROM (VALUES {values}) d(category, pct) "
        "CROSS JOIN (SELECT id FROM users ORDER BY created_at LIMIT 1) u "
        "WHERE NOT EXISTS (SELECT 1 FROM portfolio_targets)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS portfolio_targets_version")
    for column in ("valid_to", "valid_from", "floor", "band_pp"):
        op.execute(f"ALTER TABLE portfolio_targets DROP COLUMN IF EXISTS {column}")
