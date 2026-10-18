"""regras, origem da categoria e eventos de categorização (AD-16 passo 3b, Story 2.4)

Revision ID: 0019_category_rules
Revises: 0018_category_groups
Create Date: 2026-10-18

- `category_rules` ("descrição contém", `direction`, categoria, ativa, origem, `created_in_batch`),
  migradas de `categories.match_patterns` com origem `legado`:
  - gasto → regra de saída; receita → regra de entrada; transferência → ambos;
  - investimento → DUAS regras: saída → a subcategoria de investimento; entrada → o Resgate
    correspondente (D6: entrada vinda da corretora/carteira é resgate). As subcategorias de Resgates
    nascem aqui (a 2.6 move o histórico para elas);
  - padrões das categorias legado Flash Capital/Betuel apontam para Recorrente.
  A detecção de transferência interna (contas próprias + LEDGER_SELF_IDENTIFIERS) não vira regra.
- `categorization_events` (append-only: antes, depois, origem, `cause`, lote, regra).
- `transactions.category_source` ∈ {rule, suggestion, manual}, `review_status` ∈ {pending,
confirmed},
  `category_rule_id` (FK ON DELETE SET NULL). Histórico: descrição casa a regra vencedora (mais
  longa;
  empate → a mais recente) que aponta para a categoria atual → `rule`; senão `manual`; tudo
  `confirmed`. Importado sem revisão (ADR-016) → `rule` ou `suggestion`, `pending`.
Idempotente: regras únicas por (padrão, direção, categoria); backfill só onde a origem é nula.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_category_rules"
down_revision: str | None = "0018_category_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_CUTOFF = "2026-10-18 06:07:00+00"  # ADR-016
CAUSES = ("import", "review", "inline_edit", "rule_created", "reapply", "move", "migration", "undo")

# Resgate correspondente de cada subcategoria de investimento (key de investimento → key, nome).
RESGATES = {
    "invest:caixinha_rdb": ("resgate:caixinha_rdb", "Resgate Caixinha/RDB Nubank"),
    "invest:toro_b3": ("resgate:toro_b3", "Resgate Toro (B3)"),
    "invest:tesouro_nubank": ("resgate:tesouro_nubank", "Resgate Tesouro Direto Nubank"),
    "invest:renda_fixa_nubank": ("resgate:renda_fixa_nubank", "Resgate Renda Fixa Nubank"),
    "invest:cripto_nubank": ("resgate:cripto_nubank", "Resgate Cripto Nubank"),
    "invest:cripto_diversos": ("resgate:cripto_diversos", "Resgate Cripto Diversos"),
    "invest:binance": ("resgate:binance", "Resgate Binance"),
    "invest:debentures_flash": ("resgate:debentures_flash", "Resgate Debêntures Flash"),
    "invest:liquid_defi": ("resgate:liquid_defi", "Resgate Liquid/DeFi"),
}
RETARGET = {"legado:flash_capital": "trabalho:recorrente", "legado:betuel": "trabalho:recorrente"}


def _q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run(sql: str) -> None:
    for statement in sql.split(";\n"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    causes = ", ".join(_q(c) for c in CAUSES)
    _run(
        f"""
        CREATE TABLE IF NOT EXISTS category_rules (
          id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id          uuid NOT NULL DEFAULT goodies_owner_id() REFERENCES users(id),
          pattern          text NOT NULL CHECK (length(btrim(pattern)) > 0),
          direction        text NOT NULL CHECK (direction IN ('entrada', 'saida', 'ambos')),
          category_id      uuid NOT NULL REFERENCES categories(id),
          is_active        boolean NOT NULL DEFAULT true,
          origin           text NOT NULL DEFAULT 'manual'
                           CHECK (origin IN ('legado', 'review', 'manual')),
          created_in_batch uuid REFERENCES import_batches(id),
          created_at       timestamptz NOT NULL DEFAULT now(),
          UNIQUE (pattern, direction, category_id)
        );
        CREATE INDEX IF NOT EXISTS idx_category_rules_batch ON category_rules(created_in_batch);
        ALTER TABLE category_rules ENABLE ROW LEVEL SECURITY;
        CREATE TABLE IF NOT EXISTS categorization_events (
          id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id            uuid NOT NULL DEFAULT goodies_owner_id() REFERENCES users(id),
          transaction_id     uuid NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
          before_category_id uuid REFERENCES categories(id),
          after_category_id  uuid NOT NULL REFERENCES categories(id),
          source             text NOT NULL CHECK (source IN ('rule', 'suggestion', 'manual')),
          cause              text NOT NULL CHECK (cause IN ({causes})),
          batch_id           uuid REFERENCES import_batches(id),
          rule_id            uuid REFERENCES category_rules(id) ON DELETE SET NULL,
          created_at         timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_categorization_events_tx
          ON categorization_events(transaction_id);
        ALTER TABLE categorization_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_source text;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS review_status text;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_rule_id uuid
          REFERENCES category_rules(id) ON DELETE SET NULL
        """
    )

    # Subcategorias de Resgates (role resgate, grupo Resgates).
    for key, name in RESGATES.values():
        op.execute(
            f"INSERT INTO categories (name, kind, group_id, role, key) "
            f"SELECT {_q(name)}, 'income', g.id, 'resgate', {_q(key)} "
            f"FROM category_groups g WHERE g.key = 'resgates' "
            f"AND NOT EXISTS (SELECT 1 FROM categories WHERE key = {_q(key)})"
        )

    # Regras a partir dos padrões atuais.
    op.execute(
        """
        INSERT INTO category_rules (pattern, direction, category_id, origin, created_at)
        SELECT lower(btrim(p)),
               CASE c.kind WHEN 'expense' THEN 'saida' WHEN 'income' THEN 'entrada'
                           WHEN 'investment' THEN 'saida' ELSE 'ambos' END,
               c.id, 'legado', c.created_at
        FROM categories c, unnest(c.match_patterns) p
        WHERE btrim(p) <> '' AND c.key NOT LIKE 'legado:%'
        ON CONFLICT (pattern, direction, category_id) DO NOTHING
        """
    )
    for invest_key, (resgate_key, _name) in RESGATES.items():
        op.execute(
            f"""
            INSERT INTO category_rules (pattern, direction, category_id, origin, created_at)
            SELECT lower(btrim(p)), 'entrada', r.id, 'legado', c.created_at
            FROM categories c, unnest(c.match_patterns) p, categories r
            WHERE c.key = {_q(invest_key)} AND r.key = {_q(resgate_key)} AND btrim(p) <> ''
            ON CONFLICT (pattern, direction, category_id) DO NOTHING
            """
        )
    for legacy_key, target_key in RETARGET.items():
        op.execute(
            f"""
            INSERT INTO category_rules (pattern, direction, category_id, origin, created_at)
            SELECT lower(btrim(p)), 'entrada', t.id, 'legado', c.created_at
            FROM categories c, unnest(c.match_patterns) p, categories t
            WHERE c.key = {_q(legacy_key)} AND t.key = {_q(target_key)} AND btrim(p) <> ''
            ON CONFLICT (pattern, direction, category_id) DO NOTHING
            """
        )

    # Origem do histórico: a regra vencedora para a descrição e o sinal (mais longa; empate → a mais
    # recente) aponta para a categoria atual → `rule`; senão `manual`.
    op.execute(
        f"""
        WITH best AS (
          SELECT t.id AS tx_id, r.id AS rule_id, r.category_id
          FROM transactions t
          CROSS JOIN LATERAL (
            SELECT r.id, r.category_id FROM category_rules r
            WHERE r.is_active
              AND (r.direction = 'ambos'
                   OR (r.direction = 'entrada' AND t.amount > 0)
                   OR (r.direction = 'saida' AND t.amount < 0))
              AND position(r.pattern IN lower(coalesce(t.description, ''))) > 0
            ORDER BY length(r.pattern) DESC, r.created_at DESC, r.id
            LIMIT 1
          ) r
          WHERE t.category_source IS NULL
        )
        UPDATE transactions t SET
          category_source = CASE
            WHEN best.category_id = t.category_id THEN 'rule'
            WHEN t.created_at >= '{REVIEW_CUTOFF}' THEN 'suggestion'
            ELSE 'manual' END,
          category_rule_id = CASE WHEN best.category_id = t.category_id THEN best.rule_id END
        FROM best WHERE best.tx_id = t.id
        """
    )
    op.execute(
        f"""
        UPDATE transactions SET category_source = CASE
            WHEN created_at >= '{REVIEW_CUTOFF}' THEN 'suggestion' ELSE 'manual' END
        WHERE category_source IS NULL
        """
    )
    op.execute(
        f"""
        UPDATE transactions SET review_status = CASE
            WHEN created_at >= '{REVIEW_CUTOFF}' THEN 'pending' ELSE 'confirmed' END
        WHERE review_status IS NULL
        """
    )
    _run(
        """
        ALTER TABLE transactions ALTER COLUMN category_source SET DEFAULT 'suggestion';
        ALTER TABLE transactions ALTER COLUMN category_source SET NOT NULL;
        ALTER TABLE transactions ALTER COLUMN review_status SET DEFAULT 'pending';
        ALTER TABLE transactions ALTER COLUMN review_status SET NOT NULL;
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_category_source_check;
        ALTER TABLE transactions ADD CONSTRAINT transactions_category_source_check
          CHECK (category_source IN ('rule', 'suggestion', 'manual'));
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_review_status_check;
        ALTER TABLE transactions ADD CONSTRAINT transactions_review_status_check
          CHECK (review_status IN ('pending', 'confirmed'))
        """
    )


def downgrade() -> None:
    _run(
        """
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_review_status_check;
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_category_source_check;
        ALTER TABLE transactions DROP COLUMN IF EXISTS category_rule_id;
        ALTER TABLE transactions DROP COLUMN IF EXISTS review_status;
        ALTER TABLE transactions DROP COLUMN IF EXISTS category_source;
        DROP TABLE IF EXISTS categorization_events;
        DROP TABLE IF EXISTS category_rules;
        DELETE FROM categories WHERE key LIKE 'resgate:%'
        """
    )
