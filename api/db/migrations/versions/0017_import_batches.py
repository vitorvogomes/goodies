"""import_batches + lotes legacy — proveniência do histórico (AD-16 passo 2, Story 2.2)

Revision ID: 0017_import_batches
Revises: 0016_ledger_user_id
Create Date: 2026-10-18

Cria as tabelas da engine `ingest` (AD-5):
- `import_batches` (status `staged` → `applied` → `undone`; `legacy` para o histórico anterior à
v2);
- `import_batch_files` (fonte, conta ou corretora, `period_start`/`period_end`, hash do arquivo,
saldo
  informado).

`transactions` e `asset_operations` ganham `batch_id` (FK) e `source` (CHECK). O histórico ganha um
lote
`legacy` por fonte e conta/corretora, com o período tirado das próprias linhas; linhas lançadas à
mão
(ou derivadas de outras linhas) ficam com `batch_id` nulo e `source` manual/derived. Ids dos lotes
legacy
são determinísticos (md5 da fonte + conta), então a revisão é idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_import_batches"
down_revision: str | None = "0016_ledger_user_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fontes de arquivo (adapters) e as origens de linha que não vêm de arquivo.
FILE_SOURCES = ("nubank_ofx", "nubank_csv", "b3_movimentacao", "b3_negociacao", "b3_consolidado")
ROW_SOURCES = (*FILE_SOURCES, "manual", "hermes", "derived")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _run(sql: str) -> None:
    """O asyncpg não aceita vários comandos num prepared statement: um `op.execute` por comando
    (nenhum comando desta revisão tem `;` dentro de literal)."""
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run(
        f"""
        CREATE TABLE IF NOT EXISTS import_batches (
          id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id      uuid NOT NULL DEFAULT goodies_owner_id() REFERENCES users(id),
          status       text NOT NULL CHECK (status IN ('staged', 'applied', 'undone', 'legacy')),
          plan         jsonb,
          plan_hash    text,
          created_at   timestamptz NOT NULL DEFAULT now(),
          expires_at   timestamptz,
          applied_at   timestamptz,
          undone_at    timestamptz
        );
        CREATE TABLE IF NOT EXISTS import_batch_files (
          id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          batch_id               uuid NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
          user_id                uuid NOT NULL DEFAULT goodies_owner_id() REFERENCES users(id),
          source                 text NOT NULL CHECK (source IN ({_in(FILE_SOURCES)})),
          account_id             uuid REFERENCES accounts(id) ON DELETE SET NULL,
          broker                 text,
          file_name              text,
          file_hash              text,
          period_start           date,
          period_end             date,
          reported_balance       numeric(15,2),
          reported_balance_date  date,
          created_at             timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_import_batch_files_batch ON import_batch_files(batch_id);
        CREATE INDEX IF NOT EXISTS idx_import_batch_files_hash ON import_batch_files(file_hash);
        ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
        ALTER TABLE import_batch_files ENABLE ROW LEVEL SECURITY;
        """
    )
    for table in ("transactions", "asset_operations"):
        _run(
            f"""
            ALTER TABLE {table}
              ADD COLUMN IF NOT EXISTS batch_id uuid
                REFERENCES import_batches(id) ON DELETE RESTRICT,
              ADD COLUMN IF NOT EXISTS source text;
            CREATE INDEX IF NOT EXISTS idx_{table}_batch ON {table}(batch_id);
            """
        )

    # --- origem do histórico ---
    _run(
        """
        UPDATE transactions SET source = CASE
            WHEN external_id LIKE 'tesouro-sale-return:%' THEN 'manual'
            WHEN external_id IS NULL THEN 'manual'
            ELSE 'nubank_ofx' END
        WHERE source IS NULL;
        UPDATE asset_operations SET source = CASE
            WHEN broker = 'B3-negociacao' THEN 'b3_negociacao'
            WHEN broker IN ('Toro/B3', 'B3-movimentacao') THEN 'b3_movimentacao'
            WHEN external_id LIKE 'caixinha:%' THEN 'derived'
            ELSE 'manual' END
        WHERE source IS NULL;
        """
    )

    # --- lotes legacy: um por (fonte, conta) e (fonte, corretora), período das próprias linhas ---
    _run(
        """
        WITH g AS (
          SELECT source, account_id, min(date) ps, max(date) pe,
                 md5('legacy:' || source || ':' || account_id::text)::uuid AS bid
          FROM transactions
          WHERE batch_id IS NULL AND source IN ('nubank_ofx', 'nubank_csv')
          GROUP BY source, account_id
        ), b AS (
          INSERT INTO import_batches (id, status, applied_at)
          SELECT bid, 'legacy', now() FROM g ON CONFLICT (id) DO NOTHING
        )
        INSERT INTO import_batch_files (batch_id, source, account_id, period_start, period_end)
        SELECT bid, source, account_id, ps, pe FROM g
        WHERE NOT EXISTS (SELECT 1 FROM import_batch_files f WHERE f.batch_id = g.bid);

        UPDATE transactions t
           SET batch_id = md5('legacy:' || t.source || ':' || t.account_id::text)::uuid
         WHERE t.batch_id IS NULL AND t.source IN ('nubank_ofx', 'nubank_csv');

        WITH g AS (
          SELECT source, broker, min(data_operacao) ps, max(data_operacao) pe,
                 md5('legacy:' || source || ':' || broker)::uuid AS bid
          FROM asset_operations
          WHERE batch_id IS NULL AND source IN ('b3_movimentacao', 'b3_negociacao')
          GROUP BY source, broker
        ), b AS (
          INSERT INTO import_batches (id, status, applied_at)
          SELECT bid, 'legacy', now() FROM g ON CONFLICT (id) DO NOTHING
        )
        INSERT INTO import_batch_files (batch_id, source, broker, period_start, period_end)
        SELECT bid, source, broker, ps, pe FROM g
        WHERE NOT EXISTS (SELECT 1 FROM import_batch_files f WHERE f.batch_id = g.bid);

        UPDATE asset_operations o
           SET batch_id = md5('legacy:' || o.source || ':' || o.broker)::uuid
         WHERE o.batch_id IS NULL AND o.source IN ('b3_movimentacao', 'b3_negociacao');
        """
    )

    # Fecha o modelo: toda linha tem origem; linha de arquivo sempre tem lote.
    for table in ("transactions", "asset_operations"):
        _run(
            f"""
            ALTER TABLE {table} ALTER COLUMN source SET DEFAULT 'manual';
            ALTER TABLE {table} ALTER COLUMN source SET NOT NULL;
            ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_source_check;
            ALTER TABLE {table} ADD CONSTRAINT {table}_source_check
              CHECK (source IN ({_in(ROW_SOURCES)}));
            ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_batch_for_files;
            ALTER TABLE {table} ADD CONSTRAINT {table}_batch_for_files
              CHECK (source NOT IN ({_in(FILE_SOURCES)}) OR batch_id IS NOT NULL);
            """
        )


def downgrade() -> None:
    for table in ("transactions", "asset_operations"):
        _run(
            f"""
            ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_batch_for_files;
            ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_source_check;
            ALTER TABLE {table} DROP COLUMN IF EXISTS batch_id;
            ALTER TABLE {table} DROP COLUMN IF EXISTS source;
            """
        )
    _run("DROP TABLE IF EXISTS import_batch_files; DROP TABLE IF EXISTS import_batches;")
