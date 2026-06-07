"""benchmark_data — séries de benchmark (CDI/IPCA/IBOV) (m4 04-07)

Revision ID: 0011_benchmark_data
Revises: 0010_wallet_positions
Create Date: 2026-06-06

Tabela de pontos de benchmark por (série, data). O m4 popula **CDI** e **IPCA** pelo BCB
(SGS, open data); **IBOV** fica atrás da interface (deferido ao m5, story 05-03). O uso
pleno (benchmarks acumulados, retorno real, XIRR vs benchmark) é do m5 — aqui nasce só a
coleta + a tabela.

- Dado global (sem `user_id`), igual a `asset_prices`: a série é a mesma p/ todos.
- `UNIQUE (series, ref_date)` → upsert (ON CONFLICT) mantém o último valor por dia.
- **Coordenar com 05-01:** esta migration entrega SÓ `benchmark_data`; `goals` e
  `active_alerts` ficam p/ o m5 (não redefinir esta tabela lá).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_benchmark_data"
down_revision: str | None = "0010_wallet_positions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE benchmark_data (
          id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          series      text NOT NULL,           -- CDI | IPCA | IBOV
          ref_date    date NOT NULL,
          value       numeric(20, 8) NOT NULL,
          source      text NOT NULL,           -- bcb | yfinance | brapi
          fetched_at  timestamptz NOT NULL DEFAULT now(),
          UNIQUE (series, ref_date)
        );
        """
    )
    op.execute("CREATE INDEX idx_benchmark_data_series ON benchmark_data(series, ref_date);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_data CASCADE;")
