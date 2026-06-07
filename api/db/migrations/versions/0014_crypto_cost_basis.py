"""crypto_cost_basis — custo por ativo reconstruído (Tier 2, m4)

Revision ID: 0014_crypto_cost_basis
Revises: 0013_wallet_is_manual
Create Date: 2026-06-07

Custo médio POR ATIVO reconstruído de histórico de corretora/on-chain (Tier 2). Tabela
DEDICADA, **não** `asset_operations`: cripto não entra no ledger de cashflow do XIRR (o
sleeve, ancorado no ledger Nubank, segue sendo a verdade money-weighted). Aqui guardamos só
o custo-base p/ preencher o preço médio/resultado POR ATIVO em Posições (hoje "—").

Modelo pragmático (Vitor): só o custo dos trades (em BRL via câmbio histórico); a quantidade
excedente (escaneada - negociada = depósitos/Earn/convert) é tratada a CUSTO ZERO →
`traded_qty` registra o lado negociado p/ transparência do gap. `source` = 'binance' (1ª
reconstrução); novas fontes somam por (user, asset_symbol).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_crypto_cost_basis"
down_revision: str | None = "0013_wallet_is_manual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE crypto_cost_basis (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id         uuid NOT NULL REFERENCES users(id),
          asset_symbol    text NOT NULL,
          source          text NOT NULL,
          qty             numeric(36, 18) NOT NULL CHECK (qty >= 0),
          custo_total_brl numeric(20, 2)  NOT NULL CHECK (custo_total_brl >= 0),
          traded_qty      numeric(36, 18),
          computed_at     timestamptz NOT NULL DEFAULT now(),
          UNIQUE (user_id, asset_symbol, source)
        );
        """
    )
    op.execute("CREATE INDEX idx_crypto_cost_basis_user ON crypto_cost_basis(user_id);")
    op.execute("ALTER TABLE crypto_cost_basis ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS crypto_cost_basis CASCADE;")
