"""wallet_positions.is_manual — posições manuais (Liquid confidencial) (m4)

Revision ID: 0013_wallet_is_manual
Revises: 0012_defi_positions
Create Date: 2026-06-06

A Liquid (SideSwap) usa endereço CONFIDENCIAL: o esplora público não revela saldos
blinded sem a blinding key, então L-BTC/L-USDT não são escaneáveis. Entram por **entrada
manual** na mesma tabela `wallet_positions` (aparecem no /wallets junto das escaneadas,
valoradas pelo preço do m3). `is_manual=true` marca a linha como manual: o sweep do
worker NUNCA a remove (mesma ideia do `is_manual` de `asset_prices`, ADR-012).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_wallet_is_manual"
down_revision: str | None = "0012_defi_positions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE wallet_positions "
        "ADD COLUMN is_manual boolean NOT NULL DEFAULT false;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE wallet_positions DROP COLUMN IF EXISTS is_manual;")
