"""assets — ativos com chave única (AD-11, AD-16 passo 5, Story 3.2)

Revision ID: 0023_assets
Revises: 0022_alert_dismissals
Create Date: 2026-10-18

- `assets` (dono `portfolio`): `key` imutável (`b3:BBAS3`, `td:IPCA+2032`, `caixinha:turbo`,
  `crypto:BTC`), classe do enum da AD-11, `price_ref` (ticker em `asset_prices`), valoração, %CDI.
- `asset_aliases(asset_id, chain, symbol)`: como cada origem chama o ativo. Operações usam a cadeia
  da classe (`b3`, `tesouro`, `manual`); carteiras, a própria cadeia (ETH em arbitrum, ethereum e
  binance é um ativo só; HYPE na L1 e na HyperEVM também).
- `asset_operations.asset_id` e `wallet_positions.asset_id` NOT NULL, preenchidos pelo mapa
  explícito dos rótulos legados (`goodies_asset_key`); linha nova sem `asset_id` é resolvida por
  trigger (ativo novo nasce com a chave do mapa), até cada escrita passar a mandar o id.
- `portfolio_targets.class` (gerada do rótulo da classe) e `asset_id` nulo (nulo = meta da classe).
Idempotente: rodar de novo não cria ativo nem muda vínculo.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_assets"
down_revision: str | None = "0022_alert_dismissals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLASSES = ("acoes_br", "etfs", "fiis", "renda_fixa", "aposentadoria", "cripto")
# Rótulos legados da classe (portfolio/constants v1) → enum da AD-11; sem diferença de caixa (há
# operação gravada como 'cripto').
CLASS_CASE = """CASE lower(btrim({col}))
      WHEN 'ações nacionais' THEN 'acoes_br' WHEN 'etfs' THEN 'etfs' WHEN 'fiis' THEN 'fiis'
      WHEN 'renda fixa' THEN 'renda_fixa' WHEN 'aposentadoria' THEN 'aposentadoria'
      WHEN 'cripto' THEN 'cripto' END"""


def upgrade() -> None:
    classes = ", ".join(f"'{c}'" for c in CLASSES)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS assets (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          key        text NOT NULL UNIQUE,
          name       text NOT NULL,
          class      text NOT NULL CHECK (class IN ({classes})),
          price_ref  text,
          valuation  text NOT NULL DEFAULT 'mercado'
                     CHECK (valuation IN ('mercado', 'manual', 'cdi')),
          pct_cdi    numeric(7, 2),
          is_active  boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_aliases (
          asset_id uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
          chain    text NOT NULL,
          symbol   text NOT NULL,
          PRIMARY KEY (chain, symbol)
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_assets_key_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.key <> OLD.key THEN
            RAISE EXCEPTION 'assets.key é imutável (%)', OLD.key;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_assets_key_immutable ON assets")
    op.execute(
        "CREATE TRIGGER trg_assets_key_immutable BEFORE UPDATE OF key ON assets "
        "FOR EACH ROW EXECUTE FUNCTION goodies_assets_key_immutable()"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION goodies_asset_class(category text) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$ SELECT {CLASS_CASE.format(col="category")} $$
        """
    )
    # Mapa explícito rótulo legado → key (AD-11). Tesouro: "Tesouro IPCA+ 2032" → td:IPCA+2032,
    # "... com Juros Semestrais 2055" → td:IPCA+JS2055, Prefixado → PRE, Selic → SELIC.
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION goodies_asset_key(cls text, symbol text) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$
          SELECT CASE
            WHEN cls IN ('acoes_br', 'etfs', 'fiis') THEN 'b3:' || upper(symbol)
            WHEN cls = 'aposentadoria' THEN 'td:' || regexp_replace(
              regexp_replace(regexp_replace(regexp_replace(regexp_replace(
                symbol, '^Tesouro\s+', ''), 'IPCA\+\s+com Juros Semestrais', 'IPCA+JS'),
                'Prefixado', 'PRE'), 'Selic', 'SELIC'), '\s+', '', 'g')
            WHEN cls = 'renda_fixa' THEN CASE
              WHEN symbol = 'Flash-Debênture' THEN 'debenture:flash'
              WHEN symbol = 'Guanabara-CDB' THEN 'cdb:guanabara'
              WHEN symbol LIKE 'Nubank-%' THEN 'caixinha:' || lower(substr(symbol, 8))
              ELSE 'rf:' || lower(regexp_replace(symbol, '\s+', '-', 'g')) END
            WHEN cls = 'cripto' THEN 'crypto:' || upper(symbol)
          END
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_resolve_asset(p_chain text, p_symbol text, p_class text)
        RETURNS uuid LANGUAGE plpgsql AS $$
        DECLARE
          aid uuid;
          k text;
        BEGIN
          SELECT asset_id INTO aid FROM asset_aliases WHERE chain = p_chain AND symbol = p_symbol;
          IF aid IS NOT NULL THEN
            RETURN aid;
          END IF;
          IF p_class IS NULL THEN
            RAISE EXCEPTION 'classe de ativo desconhecida para % (%)', p_symbol, p_chain;
          END IF;
          k := goodies_asset_key(p_class, p_symbol);
          INSERT INTO assets (key, name, class, price_ref, valuation)
          VALUES (k, p_symbol, p_class, p_symbol,
                  CASE WHEN p_class = 'renda_fixa' THEN 'manual' ELSE 'mercado' END)
          ON CONFLICT (key) DO NOTHING;
          SELECT id INTO aid FROM assets WHERE key = k;
          INSERT INTO asset_aliases (asset_id, chain, symbol) VALUES (aid, p_chain, p_symbol)
          ON CONFLICT (chain, symbol) DO NOTHING;
          RETURN aid;
        END $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_op_chain(cls text) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$
          SELECT CASE WHEN cls IN ('acoes_br', 'etfs', 'fiis') THEN 'b3'
                      WHEN cls = 'aposentadoria' THEN 'tesouro'
                      WHEN cls = 'renda_fixa' THEN 'manual'
                      ELSE 'cripto' END
        $$
        """
    )

    # asset_operations
    op.execute(
        "ALTER TABLE asset_operations ADD COLUMN IF NOT EXISTS asset_id uuid REFERENCES assets(id)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_asset_operations_asset() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE cls text := goodies_asset_class(NEW.asset_category);
        BEGIN
          IF NEW.asset_id IS NULL OR TG_OP = 'UPDATE' THEN
            NEW.asset_id := goodies_resolve_asset(goodies_op_chain(cls), NEW.asset_symbol, cls);
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_asset_operations_asset ON asset_operations")
    op.execute(
        "CREATE TRIGGER trg_asset_operations_asset "
        "BEFORE INSERT OR UPDATE OF asset_symbol, asset_category ON asset_operations "
        "FOR EACH ROW EXECUTE FUNCTION goodies_asset_operations_asset()"
    )
    op.execute(
        """
        UPDATE asset_operations SET asset_id = goodies_resolve_asset(
          goodies_op_chain(goodies_asset_class(asset_category)), asset_symbol,
          goodies_asset_class(asset_category))
        WHERE asset_id IS NULL
        """
    )
    op.execute("ALTER TABLE asset_operations ALTER COLUMN asset_id SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_asset_operations_asset ON asset_operations (asset_id)"
    )

    # wallet_positions
    op.execute(
        "ALTER TABLE wallet_positions ADD COLUMN IF NOT EXISTS asset_id uuid REFERENCES assets(id)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_wallet_positions_asset() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.asset_id IS NULL OR TG_OP = 'UPDATE' THEN
            NEW.asset_id := goodies_resolve_asset(NEW.chain, NEW.asset_symbol, 'cripto');
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_wallet_positions_asset ON wallet_positions")
    op.execute(
        "CREATE TRIGGER trg_wallet_positions_asset "
        "BEFORE INSERT OR UPDATE OF chain, asset_symbol ON wallet_positions "
        "FOR EACH ROW EXECUTE FUNCTION goodies_wallet_positions_asset()"
    )
    op.execute(
        "UPDATE wallet_positions "
        "SET asset_id = goodies_resolve_asset(chain, asset_symbol, 'cripto') WHERE asset_id IS NULL"
    )
    op.execute("ALTER TABLE wallet_positions ALTER COLUMN asset_id SET NOT NULL")

    # portfolio_targets: classe do enum (gerada do rótulo) + ativo opcional
    op.execute(
        f"""
        ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS class text
          GENERATED ALWAYS AS ({CLASS_CASE.format(col="category")}) STORED
        """
    )
    op.execute(
        "ALTER TABLE portfolio_targets ADD COLUMN IF NOT EXISTS asset_id uuid REFERENCES assets(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE portfolio_targets DROP COLUMN IF EXISTS asset_id")
    op.execute("ALTER TABLE portfolio_targets DROP COLUMN IF EXISTS class")
    op.execute("DROP TRIGGER IF EXISTS trg_wallet_positions_asset ON wallet_positions")
    op.execute("DROP FUNCTION IF EXISTS goodies_wallet_positions_asset()")
    op.execute("ALTER TABLE wallet_positions DROP COLUMN IF EXISTS asset_id")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_operations_asset ON asset_operations")
    op.execute("DROP FUNCTION IF EXISTS goodies_asset_operations_asset()")
    op.execute("ALTER TABLE asset_operations DROP COLUMN IF EXISTS asset_id")
    op.execute("DROP FUNCTION IF EXISTS goodies_op_chain(text)")
    op.execute("DROP FUNCTION IF EXISTS goodies_resolve_asset(text, text, text)")
    op.execute("DROP FUNCTION IF EXISTS goodies_asset_key(text, text)")
    op.execute("DROP FUNCTION IF EXISTS goodies_asset_class(text)")
    op.execute("DROP TABLE IF EXISTS asset_aliases")
    op.execute("DROP TABLE IF EXISTS assets")
    op.execute("DROP FUNCTION IF EXISTS goodies_assets_key_immutable()")
