"""add users.refresh_token_hash

Revision ID: 0002_refresh_token_hash
Revises: 0001_initial_users
Create Date: 2026-06-03

Guarda o HASH do refresh token (não o token) — STORY-00-05 / ADR-006.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_refresh_token_hash"
down_revision: str | None = "0001_initial_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN refresh_token_hash text;")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS refresh_token_hash;")
