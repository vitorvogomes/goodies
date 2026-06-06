"""wallet_positions — saldos escaneados on-chain/exchange (m4)

Revision ID: 0010_wallet_positions
Revises: 0009_caixinha_classify_patterns
Create Date: 2026-06-06

Tabela do Wallet Engine (m4 — Broker Integration). Guarda o **snapshot mais recente**
do saldo (quantidade) por (usuário, chain, endereço, ativo) escaneado de Etherscan/
Solscan/Liquid/Binance. Não é histórico: o worker `wallet_scan` faz upsert (ON CONFLICT)
e mantém só a última leitura + `scanned_at` (staleness). A valoração reusa o preço do
Market Engine (m3); a reconciliação compara a Σ quantidade escaneada com a quantidade
líquida registrada em `asset_operations`.

- `numeric(36, 18)`: cobre ERC-20 (18 casas), sats e lamports sem perda.
- RLS habilitado (sem policy — usuário único no MVP, igual a asset_operations).
- DeFi/Phantom NÃO entra aqui (é entrada manual, ADR-004 — tabela própria no 04-08).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_wallet_positions"
down_revision: str | None = "0009_caixinha_classify_patterns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE wallet_positions (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id         uuid NOT NULL REFERENCES users(id),
          chain           text NOT NULL,           -- ethereum|arbitrum|solana|liquid|binance
          wallet_address  text NOT NULL,           -- endereço on-chain (ou 'binance')
          asset_symbol    text NOT NULL,           -- ETH|ARB|HYPE|SOL|L-BTC|USDT...
          quantity        numeric(36, 18) NOT NULL CHECK (quantity >= 0),
          source          text NOT NULL,           -- etherscan|solscan|liquid|binance
          scanned_at      timestamptz NOT NULL DEFAULT now(),
          created_at      timestamptz NOT NULL DEFAULT now(),
          UNIQUE (user_id, chain, wallet_address, asset_symbol)
        );
        """
    )
    op.execute("CREATE INDEX idx_wallet_positions_user ON wallet_positions(user_id);")
    op.execute(
        "CREATE INDEX idx_wallet_positions_user_symbol "
        "ON wallet_positions(user_id, asset_symbol);"
    )
    op.execute("ALTER TABLE wallet_positions ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wallet_positions CASCADE;")
