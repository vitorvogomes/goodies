"""defi_positions — posições DeFi de entrada manual (m4 04-08)

Revision ID: 0012_defi_positions
Revises: 0011_benchmark_data
Create Date: 2026-06-06

Posições DeFi (Phantom) com **entrada manual** (ADR-004) — não vêm de scan on-chain
porque exigem leitura de protocolo (ex.: xSOL/hyUSD com vencimento). Tabela DEDICADA
(não reusa `asset_operations`, que é o ledger de cashflow do XIRR e não tem conceito de
`maturity_date`). Os alertas de vencimento (04-09) leem daqui (compute-on-read).

- `user_id` + RLS (igual a asset_operations).
- `maturity_date` opcional (xSOL/hyUSD vencem 2026-09-29).
- `balance numeric(36,18)`: cobre tokens de 18 casas.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_defi_positions"
down_revision: str | None = "0011_benchmark_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE defi_positions (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id       uuid NOT NULL REFERENCES users(id),
          protocol      text,
          asset_symbol  text NOT NULL,
          balance       numeric(36, 18) NOT NULL CHECK (balance >= 0),
          maturity_date date,
          is_active     boolean NOT NULL DEFAULT true,
          notes         text,
          created_at    timestamptz NOT NULL DEFAULT now(),
          updated_at    timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_defi_positions_user ON defi_positions(user_id);")
    op.execute("ALTER TABLE defi_positions ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS defi_positions CASCADE;")
