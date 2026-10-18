"""reclassificações do histórico — resgates, faturas e Repasse (AD-16 passo 4, Story 2.6)

Revision ID: 0021_reclassificacoes
Revises: 0020_categorize_chokepoint
Create Date: 2026-10-18

- Par investimento ↔ resgate por trilho: `categories.pair_key` (`invest:x` ↔ `resgate:x`), lido por
  trânsito, bloco cripto e caixinhas (as duas keys).
- Resgates (FR-19, ADR-015): entrada em subcategoria de investimento — inclusive a que volta de
  Binance, Liquid e carteiras cripto (D6) — passa para o Resgate correspondente (receita).
- As 18 "Pagamento de fatura" em Dívidas de 2024-nov/2025 vão para "Cartão de crédito" (gasto, a
  poupança não muda); as 4 faturas em Assinaturas (abr-mai/2026) ficam.
- Repasse sai de Trabalho para Devoluções (role `devolucao`; a subcategoria e suas transações não
  mudam, só o grupo).
Cada transação que muda de subcategoria ganha linha em `categorization_events` (cause `migration`).
Idempotente: rodar de novo não acha nada a mudar.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_reclassificacoes"
down_revision: str | None = "0020_categorize_chokepoint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRILHOS = (
    "caixinha_rdb",
    "toro_b3",
    "tesouro_nubank",
    "renda_fixa_nubank",
    "cripto_nubank",
    "cripto_diversos",
    "binance",
    "debentures_flash",
    "liquid_defi",
)
FATURA_CUTOFF = "2025-12-01"  # as 18 faturas de 2024-nov/2025


def _move(where: str, target_key: str) -> None:
    """Move as transações do filtro para a subcategoria `target_key`, com evento."""
    op.execute(
        f"""
        INSERT INTO categorization_events
          (transaction_id, before_category_id, after_category_id, source, cause, batch_id)
        SELECT t.id, t.category_id, tgt.id, t.category_source, 'migration', t.batch_id
        FROM transactions t JOIN categories c ON c.id = t.category_id,
             categories tgt
        WHERE tgt.key = '{target_key}' AND t.category_id <> tgt.id AND ({where})
        """
    )
    op.execute(
        f"""
        UPDATE transactions t SET category_id = tgt.id, category = tgt.name, kind = g.kind
        FROM categories c, categories tgt JOIN category_groups g ON g.id = tgt.group_id
        WHERE c.id = t.category_id AND tgt.key = '{target_key}' AND t.category_id <> tgt.id
          AND ({where})
        """
    )


def upgrade() -> None:
    op.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS pair_key text")
    for trilho in TRILHOS:
        op.execute(
            f"UPDATE categories SET pair_key = 'resgate:{trilho}' WHERE key = 'invest:{trilho}'"
        )
        op.execute(
            f"UPDATE categories SET pair_key = 'invest:{trilho}' WHERE key = 'resgate:{trilho}'"
        )

    for trilho in TRILHOS:
        _move(f"c.key = 'invest:{trilho}' AND t.amount > 0", f"resgate:{trilho}")

    _move(
        f"c.key = 'gasto:dividas' AND t.description ILIKE '%fatura%' "
        f"AND t.date < '{FATURA_CUTOFF}'",
        "gasto:cartao_credito",
    )

    op.execute(
        """
        UPDATE categories SET role = 'devolucao',
          group_id = (SELECT id FROM category_groups WHERE key = 'devolucoes')
        WHERE key = 'trabalho:repasse' AND role <> 'devolucao'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE categories SET role = 'work_income',
          group_id = (SELECT id FROM category_groups WHERE key = 'trabalho')
        WHERE key = 'trabalho:repasse'
        """
    )
    # Desfaz as mudanças pelo histórico de eventos da própria revisão.
    op.execute(
        """
        UPDATE transactions t SET category_id = e.before_category_id, category = c.name,
          kind = g.kind
        FROM categorization_events e
          JOIN categories c ON c.id = e.before_category_id
          JOIN category_groups g ON g.id = c.group_id
        WHERE e.transaction_id = t.id AND e.cause = 'migration'
        """
    )
    op.execute("DELETE FROM categorization_events WHERE cause = 'migration'")
    op.execute("ALTER TABLE categories DROP COLUMN IF EXISTS pair_key")
