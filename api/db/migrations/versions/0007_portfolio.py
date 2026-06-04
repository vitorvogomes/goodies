"""asset_operations + portfolio_targets schema para Portfolio Engine (m2)

Revision ID: 0007_portfolio
Revises: 0006_transaction_kind
Create Date: 2026-06-04

Tabelas base do Portfolio Engine (m2):
- asset_operations: histórico de operações (compra/venda/dividendo/juros)
  - Bridge com m1: kind=investment do ledger → aportes que reconciliam m2
  - Cashflow para XIRR: compra/aporte (negativo) → venda/resgate/dividendo (positivo)
  - RLS: filtro por user_id
- portfolio_targets: metas de alocação por categoria
  - Seed STORY-02-02: 6 categorias (Ações, ETFs, FIIs, Renda Fixa, Cripto, Aposentadoria)
  - Gate m2 depende desses alvos vs. posição atual
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_portfolio"
down_revision: str | None = "0006_transaction_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. asset_operations: histórico de operações (bridge m1 → m2 + XIRR)
    op.execute(
        """
        CREATE TABLE asset_operations (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id         uuid NOT NULL REFERENCES users(id),
          broker          text NOT NULL,
          asset_symbol    text NOT NULL,
          asset_category  text NOT NULL,
          tipo            text NOT NULL CHECK (tipo IN ('compra', 'venda',
                          'dividendo', 'juros', 'aporte', 'resgate')),
          quantidade      numeric(20, 8) NOT NULL CHECK (quantidade > 0),
          valor_unitario  numeric(15, 6) NOT NULL CHECK (valor_unitario >= 0),
          data_operacao   date NOT NULL,
          notes           text,
          external_id     text,
          created_at      timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # Índices para asset_operations
    op.execute(
        "CREATE INDEX idx_asset_operations_user ON asset_operations(user_id);"
    )
    op.execute(
        "CREATE INDEX idx_asset_operations_symbol ON asset_operations(user_id, asset_symbol);"
    )
    op.execute(
        "CREATE INDEX idx_asset_operations_date ON asset_operations(data_operacao);"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_asset_operations_external ON asset_operations(external_id) WHERE external_id IS NOT NULL;"  # noqa: E501
    )

    # RLS para asset_operations
    op.execute("ALTER TABLE asset_operations ENABLE ROW LEVEL SECURITY;")

    # 2. portfolio_targets: metas de alocação
    op.execute(
        """
        CREATE TABLE portfolio_targets (
          id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id     uuid NOT NULL REFERENCES users(id),
          category    text NOT NULL,
          target_pct  numeric(5, 2) NOT NULL CHECK (target_pct > 0 AND target_pct <= 100),
          created_at  timestamptz NOT NULL DEFAULT now(),
          UNIQUE (user_id, category)
        );
        """
    )

    # RLS para portfolio_targets
    op.execute("ALTER TABLE portfolio_targets ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_targets CASCADE;")
    op.execute("DROP TABLE IF EXISTS asset_operations CASCADE;")
