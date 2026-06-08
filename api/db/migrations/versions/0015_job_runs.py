"""job_runs — heartbeat por job (Pilar 0: catch-up local + frescor)

Revision ID: 0015_job_runs
Revises: 0014_crypto_cost_basis
Create Date: 2026-06-08

Prova de vida por job de atualização. O modelo é local-on-demand: `refresh_stale`
roda só os jobs vencidos quando o app abre / no botão "Atualizar tudo", e grava aqui
a última execução. O painel de frescor lê esta tabela. Estado de SISTEMA (não dado de
usuário, single-user) -> sem user_id, sem RLS. `stats` guarda o retorno do worker.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_job_runs"
down_revision: str | None = "0014_crypto_cost_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE job_runs (
          job      text PRIMARY KEY,
          last_run timestamptz NOT NULL,
          ok       boolean NOT NULL,
          error    text,
          stats    jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_runs CASCADE;")
