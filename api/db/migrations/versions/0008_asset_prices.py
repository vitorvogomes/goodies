"""asset_prices — preços manuais para valoração de posições (m2)

Revision ID: 0008_asset_prices
Revises: 0007_portfolio
Create Date: 2026-06-04

Tabela de preços por ticker para o Portfolio Engine (m2). Em m2 não há Market
Engine (preços automáticos chegam no m3), então a valoração de posições usa o
último preço **manual** informado pelo Vitor (is_manual=true).

- Dado de mercado global (sem user_id): preço de um ticker é o mesmo para todos.
- PK por ticker → upsert (ON CONFLICT) mantém apenas o último preço.
- Compatível com o m3: o worker de preços fará upsert com source='brapi'/'coingecko'
  e is_manual=false sobre a mesma tabela.
- Fallback (ADR-004): ausência de preço → posição com valor null/stale, nunca 5xx.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_asset_prices"
down_revision: str | None = "0007_portfolio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE asset_prices (
          ticker      text PRIMARY KEY,
          price_brl   numeric(20, 8) NOT NULL,
          price_usd   numeric(20, 8),
          source      text NOT NULL DEFAULT 'manual',
          is_manual   boolean NOT NULL DEFAULT true,
          fetched_at  timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS asset_prices CASCADE;")
