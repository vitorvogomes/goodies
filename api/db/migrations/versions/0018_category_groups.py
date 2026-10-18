"""categorias em dois níveis — grupos, roles, keys e category_id (AD-16 passo 3a, Story 2.3)

Revision ID: 0018_category_groups
Revises: 0017_import_batches
Create Date: 2026-10-18

- `category_groups` (kind = tipo de movimento) com os grupos aprovados no party mode + dois grupos
de
  sistema ("Entrada a classificar" / "Saída a classificar").
- `categories` ganha `group_id`, `role` (CHECK) e `key` (imutável, única); "Cripto Nubnak" vira
  "Cripto Nubank"; nascem "Recorrente", "Cartão de crédito" e as duas de sistema.
- `transactions.category_id` (NOT NULL) e `fixed_costs.category_id` pelo MAPA EXPLÍCITO abaixo
  (nome legado, kind gravado) → subcategoria. `transactions.payer` guarda o pagador: Flash Capital e
  Betuel viram Recorrente com o pagador preservado (delta esperado). "outros" importado sem revisão
  (ADR-016, desde 2026-10-18T06:07Z) vai para "a classificar"; o "outros" curado fica em Outros.
- A coluna de texto `category` continua (sai na Story 10.6) e passa a ter o nome da subcategoria.
- Trigger TRANSITÓRIO: caminho v1 que grava só o nome ganha o `category_id` pelo nome. Sai na Story
  2.5, quando toda escrita passa por `ledger.service.categorize()`.
Idempotente: grupos e categorias por `key` (ON CONFLICT), mapa só onde `category_id` é nulo.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_category_groups"
down_revision: str | None = "0017_import_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = (
    "work_income",
    "resgate",
    "devolucao",
    "divida",
    "consumo",
    "investimento",
    "transferencia",
    "a_classificar",
)
KINDS = ("income", "expense", "investment", "transfer")
REVIEW_CUTOFF = "2026-10-18 06:07:00+00"  # ADR-016: importado depois disto não foi revisado

# (key, nome, kind, sistema)
GROUPS = (
    ("casa", "Casa", "expense", False),
    ("alimentacao", "Alimentação", "expense", False),
    ("transporte", "Transporte", "expense", False),
    ("lazer", "Lazer", "expense", False),
    ("saude_educacao", "Saúde e educação", "expense", False),
    ("obrigacoes", "Obrigações", "expense", False),
    ("outros", "Outros", "expense", False),
    ("trabalho", "Trabalho", "income", False),
    ("resgates", "Resgates", "income", False),
    ("devolucoes", "Devoluções", "income", False),
    ("investimentos", "Investimentos", "investment", False),
    ("transferencias", "Transferências", "transfer", False),
    ("entrada_a_classificar", "Entrada a classificar", "income", True),
    ("saida_a_classificar", "Saída a classificar", "expense", True),
)

# key da subcategoria → (nome legado atual, nome final, grupo, role, ativa)
CATEGORIES = {
    "gasto:moradia": ("Moradia", "Moradia", "casa", "consumo", True),
    "gasto:assinaturas": ("Assinaturas", "Assinaturas", "casa", "consumo", True),
    "gasto:setup": ("Setup", "Setup", "casa", "consumo", True),
    "gasto:comida_fora": ("Comida Fora", "Comida Fora", "alimentacao", "consumo", True),
    "gasto:alimentacao": ("Alimentação", "Alimentação", "alimentacao", "consumo", True),
    "gasto:transporte": ("Transporte", "Transporte", "transporte", "consumo", True),
    "gasto:carro": ("Carro", "Carro", "transporte", "consumo", True),
    "gasto:pitbike": ("PitBike", "PitBike", "transporte", "consumo", True),
    "gasto:viagem": ("Viagem", "Viagem", "lazer", "consumo", True),
    "gasto:lazer": ("Lazer", "Lazer", "lazer", "consumo", True),
    "gasto:esportes": ("Esportes", "Esportes", "lazer", "consumo", True),
    "gasto:ganja": ("Ganja", "Ganja", "lazer", "consumo", True),
    "gasto:saude": ("Saúde", "Saúde", "saude_educacao", "consumo", True),
    "gasto:educacao": ("Educação", "Educação", "saude_educacao", "consumo", True),
    "gasto:impostos": ("Impostos", "Impostos", "obrigacoes", "consumo", True),
    "gasto:dividas": ("Dívidas", "Dívidas", "obrigacoes", "divida", True),
    "gasto:emergencia": ("Emergência", "Emergência", "outros", "consumo", True),
    "gasto:outros": ("outros", "outros", "outros", "consumo", True),
    "gasto:estorno": ("Estrono", "Estrono", "outros", "consumo", False),  # 0 transações
    "gasto:cartao_credito": (None, "Cartão de crédito", "outros", "consumo", True),
    "trabalho:recorrente": (None, "Recorrente", "trabalho", "work_income", True),
    "trabalho:extra": ("Extra", "Extra", "trabalho", "work_income", True),
    # Repasse muda para Devoluções na Story 2.6 (reclassificação com eventos e deltas).
    "trabalho:repasse": ("Repasse", "Repasse", "trabalho", "work_income", True),
    "legado:flash_capital": ("Flash Capital", "Flash Capital", "trabalho", "work_income", False),
    "legado:betuel": ("Betuel", "Betuel", "trabalho", "work_income", False),
    "devolucao:reembolso": ("Reembolso", "Reembolso", "devolucoes", "devolucao", True),
    "invest:caixinha_rdb": (
        "Caixinha/RDB Nubank", "Caixinha/RDB Nubank", "investimentos", "investimento", True,
    ),
    "invest:toro_b3": ("Toro (B3)", "Toro (B3)", "investimentos", "investimento", True),
    "invest:tesouro_nubank": (
        "Tesouro Direto Nubank", "Tesouro Direto Nubank", "investimentos", "investimento", True,
    ),
    "invest:renda_fixa_nubank": (
        "Renda Fixa Nubank", "Renda Fixa Nubank", "investimentos", "investimento", True,
    ),
    "invest:cripto_nubank": (
        "Cripto Nubnak", "Cripto Nubank", "investimentos", "investimento", True,
    ),
    "invest:cripto_diversos": (
        "Cripto Diversos", "Cripto Diversos", "investimentos", "investimento", True,
    ),
    "invest:binance": ("Binance", "Binance", "investimentos", "investimento", True),
    "invest:debentures_flash": (
        "Flash Capital debêntures", "Flash Capital debêntures", "investimentos", "investimento",
        True,
    ),
    "invest:liquid_defi": ("Liquid/DeFi", "Liquid/DeFi", "investimentos", "investimento", True),
    "transfer:interna": (
        "Transferência interna", "Transferência interna", "transferencias", "transferencia", True,
    ),
    "sistema:entrada_a_classificar": (
        None, "Entrada a classificar", "entrada_a_classificar", "a_classificar", True,
    ),
    "sistema:saida_a_classificar": (
        None, "Saída a classificar", "saida_a_classificar", "a_classificar", True,
    ),
}

# Mapa explícito das transações: (nome legado, kind gravado) → key da subcategoria.
# "outros" curado (antes do corte do ADR-016) fica em Outros; o importado depois vai para "a
# classificar".
TX_MAP = {
    ("Flash Capital", "income"): "trabalho:recorrente",
    ("Betuel", "income"): "trabalho:recorrente",
    ("outros", "income"): "sistema:entrada_a_classificar",
}
_PAYER_FROM = ("Flash Capital", "Betuel")


def _q(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


def _in(values: Sequence[str]) -> str:
    return ", ".join(_q(v) for v in values)


def _run(sql: str) -> None:
    for statement in sql.split(";\n"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run(
        f"""
        CREATE TABLE IF NOT EXISTS category_groups (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id    uuid NOT NULL DEFAULT goodies_owner_id() REFERENCES users(id),
          key        text NOT NULL UNIQUE,
          name       text NOT NULL,
          kind       text NOT NULL CHECK (kind IN ({_in(KINDS)})),
          is_system  boolean NOT NULL DEFAULT false,
          is_active  boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        ALTER TABLE category_groups ENABLE ROW LEVEL SECURITY;
        ALTER TABLE categories ADD COLUMN IF NOT EXISTS group_id uuid
          REFERENCES category_groups(id);
        ALTER TABLE categories ADD COLUMN IF NOT EXISTS role text;
        ALTER TABLE categories ADD COLUMN IF NOT EXISTS key text;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_id uuid
          REFERENCES categories(id);
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS payer text;
        ALTER TABLE fixed_costs ADD COLUMN IF NOT EXISTS category_id uuid REFERENCES categories(id)
        """
    )
    for key, name, kind, system in GROUPS:
        op.execute(
            f"INSERT INTO category_groups (key, name, kind, is_system) "
            f"VALUES ({_q(key)}, {_q(name)}, {_q(kind)}, {str(system).lower()}) "
            f"ON CONFLICT (key) DO NOTHING"
        )
    kind_of = {g[0]: g[2] for g in GROUPS}
    for key, (legacy, name, group, role, active) in CATEGORIES.items():
        set_cols = (
            f"group_id = (SELECT id FROM category_groups WHERE key = {_q(group)}), "
            f"role = {_q(role)}, key = {_q(key)}, name = {_q(name)}, "
            f"kind = {_q(kind_of[group])}, is_active = {str(active).lower()}"
        )
        if legacy is not None:
            op.execute(
                f"UPDATE categories SET {set_cols} WHERE key IS NULL AND name = {_q(legacy)}"
            )
        op.execute(
            f"INSERT INTO categories (name, kind, is_active, group_id, role, key) "
            f"SELECT {_q(name)}, {_q(kind_of[group])}, {str(active).lower()}, "
            f"(SELECT id FROM category_groups WHERE key = {_q(group)}), {_q(role)}, {_q(key)} "
            f"WHERE NOT EXISTS (SELECT 1 FROM categories WHERE key = {_q(key)})"
        )

    # Categoria fora do mapa (criada no CRUD v1 ou em teste): grupo padrão do kind e key `custom:`.
    # Na base real o mapa cobre todas — o teste dados_reais da 2.3 exige zero `custom:`.
    op.execute(
        """
        UPDATE categories c SET
          group_id = g.id,
          role = CASE c.kind WHEN 'income' THEN 'work_income' WHEN 'investment' THEN 'investimento'
                             WHEN 'transfer' THEN 'transferencia' ELSE 'consumo' END,
          key = 'custom:' || left(md5(c.id::text), 12)
        FROM category_groups g
        WHERE c.key IS NULL AND g.key = CASE c.kind
          WHEN 'income' THEN 'trabalho' WHEN 'investment' THEN 'investimentos'
          WHEN 'transfer' THEN 'transferencias' ELSE 'outros' END
        """
    )

    # Pagador antes do remapeamento (o nome legado da receita é o pagador).
    op.execute(
        f"UPDATE transactions SET payer = category "
        f"WHERE payer IS NULL AND category IN ({_in(_PAYER_FROM)}) AND kind = 'income'"
    )
    for (legacy, kind), key in TX_MAP.items():
        op.execute(
            f"UPDATE transactions SET category_id = "
            f"(SELECT id FROM categories WHERE key = {_q(key)}) "
            f"WHERE category_id IS NULL AND category = {_q(legacy)} AND kind = {_q(kind)}"
        )
    op.execute(
        f"UPDATE transactions SET category_id = "
        f"(SELECT id FROM categories WHERE key = 'sistema:saida_a_classificar') "
        f"WHERE category_id IS NULL AND category = 'outros' AND kind = 'expense' "
        f"AND created_at >= '{REVIEW_CUTOFF}'"
    )
    # Demais: pelo nome legado (antes do renome) → key do mapa.
    for key, (legacy, *_rest) in CATEGORIES.items():
        if legacy is None:
            continue
        op.execute(
            f"UPDATE transactions SET category_id = "
            f"(SELECT id FROM categories WHERE key = {_q(key)}) "
            f"WHERE category_id IS NULL AND category = {_q(legacy)}"
        )
        op.execute(
            f"UPDATE fixed_costs SET category_id = "
            f"(SELECT id FROM categories WHERE key = {_q(key)}) "
            f"WHERE category_id IS NULL AND category = {_q(legacy)}"
        )
    # Texto legado = nome da subcategoria (esquema duplo até a 10.6).
    _run(
        """
        UPDATE transactions t SET category = c.name FROM categories c
         WHERE c.id = t.category_id AND t.category IS DISTINCT FROM c.name;
        UPDATE fixed_costs f SET category = c.name FROM categories c
         WHERE c.id = f.category_id AND f.category IS DISTINCT FROM c.name
        """
    )

    _run(
        f"""
        ALTER TABLE categories ALTER COLUMN group_id SET NOT NULL;
        ALTER TABLE categories ALTER COLUMN role SET NOT NULL;
        ALTER TABLE categories ALTER COLUMN key SET NOT NULL;
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_role_check;
        ALTER TABLE categories ADD CONSTRAINT categories_role_check CHECK (role IN ({_in(ROLES)}));
        CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_key ON categories(key);
        ALTER TABLE transactions ALTER COLUMN category_id SET NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_transactions_category_id ON transactions(category_id)
        """
    )

    # Trigger transitório (sai na Story 2.5): caminho v1 que grava só o nome ganha o category_id.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_sync_category_id() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' OR NEW.category IS DISTINCT FROM OLD.category THEN
            NEW.category_id := COALESCE(
              (SELECT id FROM categories WHERE name = NEW.category),
              CASE WHEN TG_OP = 'INSERT' THEN NEW.category_id END
            );
            -- Nome desconhecido (texto livre de caminho v1): nunca sem categoria (AD-6).
            IF NEW.category_id IS NULL AND TG_TABLE_NAME = 'transactions' THEN
              NEW.category_id := (SELECT id FROM categories WHERE key = CASE
                WHEN NEW.amount > 0 THEN 'sistema:entrada_a_classificar'
                ELSE 'sistema:saida_a_classificar' END);
            END IF;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    # Categoria criada sem grupo (CRUD v1, testes): grupo padrão do tipo, role padrão, key estável.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION goodies_category_defaults() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.group_id IS NULL THEN
            NEW.group_id := (SELECT id FROM category_groups WHERE key = CASE NEW.kind
              WHEN 'income' THEN 'trabalho' WHEN 'investment' THEN 'investimentos'
              WHEN 'transfer' THEN 'transferencias' ELSE 'outros' END);
          END IF;
          IF NEW.role IS NULL THEN
            NEW.role := CASE NEW.kind WHEN 'income' THEN 'work_income'
              WHEN 'investment' THEN 'investimento' WHEN 'transfer' THEN 'transferencia'
              ELSE 'consumo' END;
          END IF;
          IF NEW.key IS NULL THEN
            NEW.key := 'custom:' || left(md5(NEW.id::text), 12);
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_categories_defaults ON categories")
    op.execute(
        "CREATE TRIGGER trg_categories_defaults BEFORE INSERT ON categories "
        "FOR EACH ROW EXECUTE FUNCTION goodies_category_defaults()"
    )
    for table in ("transactions", "fixed_costs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_category_sync ON {table}")
        op.execute(
            f"CREATE TRIGGER trg_{table}_category_sync BEFORE INSERT OR UPDATE OF category "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION goodies_sync_category_id()"
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_categories_defaults ON categories")
    op.execute("DROP FUNCTION IF EXISTS goodies_category_defaults()")
    for table in ("transactions", "fixed_costs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_category_sync ON {table}")
    op.execute("DROP FUNCTION IF EXISTS goodies_sync_category_id()")
    # Volta os nomes legados do texto e das categorias renomeadas/fundidas.
    op.execute(
        "UPDATE transactions SET category = payer WHERE payer IN ('Flash Capital', 'Betuel') "
        "AND category = 'Recorrente'"
    )
    op.execute("UPDATE transactions SET category = 'outros' WHERE category LIKE '% a classificar'")
    op.execute(
        "UPDATE transactions SET category = 'Cripto Nubnak' WHERE category = 'Cripto Nubank'"
    )
    op.execute("UPDATE categories SET name = 'Cripto Nubnak' WHERE key = 'invest:cripto_nubank'")
    op.execute(
        "UPDATE categories SET is_active = true "
        "WHERE key IN ('legado:flash_capital', 'legado:betuel')"
    )
    op.execute(
        "DELETE FROM categories WHERE key IN ('gasto:cartao_credito', 'trabalho:recorrente', "
        "'sistema:entrada_a_classificar', 'sistema:saida_a_classificar')"
    )
    _run(
        """
        ALTER TABLE fixed_costs DROP COLUMN IF EXISTS category_id;
        ALTER TABLE transactions DROP COLUMN IF EXISTS payer;
        ALTER TABLE transactions DROP COLUMN IF EXISTS category_id;
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_role_check;
        DROP INDEX IF EXISTS uq_categories_key;
        ALTER TABLE categories DROP COLUMN IF EXISTS key;
        ALTER TABLE categories DROP COLUMN IF EXISTS role;
        ALTER TABLE categories DROP COLUMN IF EXISTS group_id;
        DROP TABLE IF EXISTS category_groups
        """
    )
