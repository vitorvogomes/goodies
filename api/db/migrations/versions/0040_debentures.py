"""debentures + debenture_contributions — debêntures cadastradas no app (Story 7.6)

Revision ID: 0040_debentures
Revises: 0039_transaction_asset
Create Date: 2026-10-18

Dona `portfolio`.
- `assets.valuation` ganha `taxa` (valorada pela taxa cadastrada: debentures-flash/formula.md).
- `debentures`: uma por ativo — emissor, rótulo da taxa, fator mensal (% a.m.), início, vencimento.
- `debenture_contributions`: o aporte sugerido na Revisão (transação, debênture, valor, status
  suggested/confirmed/dismissed) e a operação criada quando confirmado.
- Dado: a debênture Flash (Pré 24% a.a., fator 1,78% a.m.) é cadastrada sobre o ativo que já
  existe; as integralizações que já estão em `asset_operations` (do seed antigo) são LIGADAS às
  transações do trilho `invest:debentures_flash` de mesma data e valor (sem reinserir), `protected`
  (curadoria) e registradas como contribuições `confirmed`. O JSON fica só como conferência.
Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0040_debentures"
down_revision: str | None = "0039_transaction_asset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UPGRADE = (
    "ALTER TABLE assets DROP CONSTRAINT IF EXISTS assets_valuation_check",
    "ALTER TABLE assets ADD CONSTRAINT assets_valuation_check "
    "CHECK (valuation IN ('mercado', 'manual', 'cdi', 'taxa'))",
    """
    CREATE TABLE IF NOT EXISTS debentures (
      id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      asset_id       uuid NOT NULL UNIQUE REFERENCES assets(id) ON DELETE CASCADE,
      issuer         text NOT NULL,
      rate_label     text NOT NULL,
      monthly_factor numeric(9, 6) NOT NULL CHECK (monthly_factor > 0),
      start_date     date NOT NULL,
      maturity_date  date,
      created_at     timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS debenture_contributions (
      id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      transaction_id uuid NOT NULL UNIQUE REFERENCES transactions(id) ON DELETE CASCADE,
      debenture_id   uuid NOT NULL REFERENCES debentures(id) ON DELETE CASCADE,
      amount         numeric(15, 2) NOT NULL CHECK (amount > 0),
      status         text NOT NULL CHECK (status IN ('suggested', 'confirmed', 'dismissed')),
      operation_id   uuid REFERENCES asset_operations(id) ON DELETE SET NULL,
      created_at     timestamptz NOT NULL DEFAULT now(),
      updated_at     timestamptz NOT NULL DEFAULT now()
    )
    """,
    "UPDATE assets SET valuation = 'taxa' WHERE key = 'debenture:flash'",
    """
    INSERT INTO debentures (asset_id, issuer, rate_label, monthly_factor, start_date)
    SELECT a.id, 'Flash', 'Pré 24% a.a.', 1.78,
           coalesce((SELECT min(data_operacao) FROM asset_operations o WHERE o.asset_id = a.id),
                    DATE '2025-07-01')
    FROM assets a WHERE a.key = 'debenture:flash'
    ON CONFLICT (asset_id) DO NOTHING
    """,
    # liga integralização ↔ transação (mesma data e valor, 1:1 pela ordem)
    """
    WITH ops AS (
      SELECT o.id, o.data_operacao AS d, o.quantidade * o.valor_unitario AS v,
             row_number() OVER (PARTITION BY o.data_operacao, o.quantidade * o.valor_unitario
                                ORDER BY o.id) AS n
      FROM asset_operations o JOIN assets a ON a.id = o.asset_id
      WHERE a.key = 'debenture:flash' AND o.tipo = 'aporte' AND o.transaction_id IS NULL
    ), txs AS (
      SELECT t.id, t.date AS d, -t.amount AS v,
             row_number() OVER (PARTITION BY t.date, t.amount ORDER BY t.id) AS n
      FROM transactions t JOIN categories c ON c.id = t.category_id
      WHERE c.key = 'invest:debentures_flash' AND t.amount < 0
        AND NOT EXISTS (SELECT 1 FROM asset_operations x WHERE x.transaction_id = t.id)
    )
    UPDATE asset_operations o SET transaction_id = txs.id, protected = true
    FROM ops JOIN txs ON txs.d = ops.d AND txs.v = ops.v AND txs.n = ops.n
    WHERE o.id = ops.id
    """,
    """
    INSERT INTO debenture_contributions (transaction_id, debenture_id, amount, status, operation_id)
    SELECT o.transaction_id, d.id, o.quantidade * o.valor_unitario, 'confirmed', o.id
    FROM asset_operations o JOIN debentures d ON d.asset_id = o.asset_id
    WHERE o.transaction_id IS NOT NULL AND o.tipo = 'aporte'
    ON CONFLICT (transaction_id) DO NOTHING
    """,
    "UPDATE transactions t SET asset_id = o.asset_id FROM asset_operations o "
    "JOIN debentures d ON d.asset_id = o.asset_id "
    "WHERE o.transaction_id = t.id AND t.asset_id IS DISTINCT FROM o.asset_id",
    "UPDATE asset_prices p SET is_manual = false, source = 'taxa' FROM assets a "
    "WHERE a.valuation = 'taxa' AND p.ticker = a.price_ref",
)


def upgrade() -> None:
    for statement in _UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS debenture_contributions")
    op.execute("DROP TABLE IF EXISTS debentures")
    op.execute("UPDATE assets SET valuation = 'manual' WHERE valuation = 'taxa'")
    op.execute("ALTER TABLE assets DROP CONSTRAINT IF EXISTS assets_valuation_check")
    op.execute(
        "ALTER TABLE assets ADD CONSTRAINT assets_valuation_check "
        "CHECK (valuation IN ('mercado', 'manual', 'cdi'))"
    )
