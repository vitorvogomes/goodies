"""asset_price_history + wallet_position_history — preço e carteira de cada dia (AD-8, Story 5.1)

Revision ID: 0029_history
Revises: 0028_job_last_success
Create Date: 2026-10-18

- `asset_price_history` (dona `market`): um preço por ticker e dia (o último do dia vence),
  escrito por trigger a cada gravação em `asset_prices` — worker, preço manual ou script. Base do
  valor de um mês passado: preço até `as_of`, nunca o de hoje.
- `wallet_position_history` (dona `wallet`): uma linha por ativo, cadeia, endereço e dia, escrita
  por trigger em `wallet_positions`; posição que sai da carteira grava quantidade 0 naquele dia.
Dia = data em Brasília. Começa com o estado atual (backfill de uma linha por preço e posição).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_history"
down_revision: str | None = "0028_job_last_success"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DAY = "(({col} AT TIME ZONE 'America/Sao_Paulo')::date)"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_price_history (
          ticker    text NOT NULL,
          ref_date  date NOT NULL,
          price_brl numeric(20, 8) NOT NULL,
          price_usd numeric(20, 8),
          source    text NOT NULL,
          is_manual boolean NOT NULL DEFAULT false,
          PRIMARY KEY (ticker, ref_date)
        )
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION goodies_price_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          INSERT INTO asset_price_history
            (ticker, ref_date, price_brl, price_usd, source, is_manual)
          VALUES (NEW.ticker, {_DAY.format(col="NEW.fetched_at")}, NEW.price_brl, NEW.price_usd,
                  NEW.source, NEW.is_manual)
          ON CONFLICT (ticker, ref_date) DO UPDATE SET
            price_brl = EXCLUDED.price_brl, price_usd = EXCLUDED.price_usd,
            source = EXCLUDED.source, is_manual = EXCLUDED.is_manual;
          RETURN NULL;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_price_history ON asset_prices")
    op.execute(
        "CREATE TRIGGER trg_price_history AFTER INSERT OR UPDATE ON asset_prices "
        "FOR EACH ROW EXECUTE FUNCTION goodies_price_history()"
    )
    op.execute(
        f"""
        INSERT INTO asset_price_history (ticker, ref_date, price_brl, price_usd, source, is_manual)
        SELECT ticker, {_DAY.format(col="fetched_at")}, price_brl, price_usd, source, is_manual
        FROM asset_prices
        ON CONFLICT (ticker, ref_date) DO NOTHING
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_position_history (
          asset_id       uuid NOT NULL REFERENCES assets(id),
          chain          text NOT NULL,
          wallet_address text NOT NULL,
          ref_date       date NOT NULL,
          quantity       numeric(30, 12) NOT NULL,
          source         text NOT NULL,
          PRIMARY KEY (asset_id, chain, wallet_address, ref_date)
        )
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION goodies_wallet_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          day date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            INSERT INTO wallet_position_history
              (asset_id, chain, wallet_address, ref_date, quantity, source)
            VALUES (OLD.asset_id, OLD.chain, OLD.wallet_address, day, 0, OLD.source)
            ON CONFLICT (asset_id, chain, wallet_address, ref_date) DO UPDATE SET quantity = 0;
            RETURN NULL;
          END IF;
          INSERT INTO wallet_position_history
            (asset_id, chain, wallet_address, ref_date, quantity, source)
          VALUES (NEW.asset_id, NEW.chain, NEW.wallet_address,
                  {_DAY.format(col="NEW.scanned_at")}, NEW.quantity, NEW.source)
          ON CONFLICT (asset_id, chain, wallet_address, ref_date) DO UPDATE SET
            quantity = EXCLUDED.quantity, source = EXCLUDED.source;
          RETURN NULL;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_wallet_history ON wallet_positions")
    op.execute(
        "CREATE TRIGGER trg_wallet_history AFTER INSERT OR UPDATE OR DELETE ON wallet_positions "
        "FOR EACH ROW EXECUTE FUNCTION goodies_wallet_history()"
    )
    op.execute(
        f"""
        INSERT INTO wallet_position_history
          (asset_id, chain, wallet_address, ref_date, quantity, source)
        SELECT asset_id, chain, wallet_address, {_DAY.format(col="scanned_at")}, quantity, source
        FROM wallet_positions
        ON CONFLICT (asset_id, chain, wallet_address, ref_date) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_wallet_history ON wallet_positions")
    op.execute("DROP FUNCTION IF EXISTS goodies_wallet_history()")
    op.execute("DROP TABLE IF EXISTS wallet_position_history")
    op.execute("DROP TRIGGER IF EXISTS trg_price_history ON asset_prices")
    op.execute("DROP FUNCTION IF EXISTS goodies_price_history()")
    op.execute("DROP TABLE IF EXISTS asset_price_history")
