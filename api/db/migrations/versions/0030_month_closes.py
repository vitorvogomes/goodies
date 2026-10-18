"""month_closes + month_summary_totals + month_summary_lines — fechamento de mês (AD-8, Story 5.3)

Revision ID: 0030_month_closes
Revises: 0029_history
Create Date: 2026-10-18

Dona `closing`. Fechar grava uma versão (1, 2, … — reabrir e fechar de novo cria a próxima; nenhuma
é apagada) com o resumo de `build_month_summary` congelado:
- `month_closes`: mês, versão, status (closed/reopened), quando, cobertura por fonte (método de
  valoração), confirmações "fechar mesmo assim", origem (live/retro) e `dirty` (ajuste depois de
  fechado, Story 5.6);
- `month_summary_totals`: **todos** os termos da AD-7 (mais valor investido, aplicado, resultado e
  saldo conferido), nulos aceitos — o motivo de cada nulo fica em `unavailable`;
- `month_summary_lines`: as quebras (`metric`, `dimension_kind`, `dimension_id` text com tipo fixo
  por `dimension_kind`, `flow_date`, `value`), inclusive os fluxos líquidos por classe e data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030_month_closes"
down_revision: str | None = "0029_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY_TERMS = (
    "receitas",
    "trabalho",
    "resgates",
    "devolucoes",
    "gastos",
    "consumido",
    "investido",
    "resultado_mes",
    "saldo_contas",
    "a_caminho",
    "caixa_corretora",
    "valor_investido",
    "patrimonio",
    "aplicado",
    "resultado_investimentos",
    "disponivel",
    "restante",
    "restante_sem_resgates",
    "consumo_financiado",
    "realizado",
    "pendente",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS month_closes (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          month         date NOT NULL CHECK (extract(day FROM month) = 1),
          version       int NOT NULL CHECK (version >= 1),
          status        text NOT NULL CHECK (status IN ('closed', 'reopened')),
          closed_at     timestamptz NOT NULL DEFAULT now(),
          reopened_at   timestamptz,
          coverage      jsonb NOT NULL DEFAULT '{}'::jsonb,
          confirmations jsonb NOT NULL DEFAULT '[]'::jsonb,
          origin        text NOT NULL DEFAULT 'live' CHECK (origin IN ('live', 'retro')),
          dirty         boolean NOT NULL DEFAULT false,
          UNIQUE (month, version)
        )
        """
    )
    money = ",\n          ".join(f"{t} numeric(15, 2)" for t in MONEY_TERMS)
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS month_summary_totals (
          month         date NOT NULL,
          version       int NOT NULL,
          as_of         date NOT NULL,
          {money},
          taxa_poupanca numeric(9, 4),
          rentabilidade numeric(9, 4),
          saldo_conferido boolean,
          unavailable   jsonb NOT NULL DEFAULT '{{}}'::jsonb,
          PRIMARY KEY (month, version),
          FOREIGN KEY (month, version) REFERENCES month_closes (month, version) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS month_summary_lines (
          month          date NOT NULL,
          version        int NOT NULL,
          metric         text NOT NULL,
          dimension_kind text NOT NULL
                         CHECK (dimension_kind IN ('category', 'class', 'asset', 'goal',
                                                   'account', 'payer')),
          dimension_id   text NOT NULL,
          flow_date      date,
          value          numeric(15, 2) NOT NULL,
          FOREIGN KEY (month, version) REFERENCES month_closes (month, version) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_month_summary_lines ON month_summary_lines (month, version)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS month_summary_lines")
    op.execute("DROP TABLE IF EXISTS month_summary_totals")
    op.execute("DROP TABLE IF EXISTS month_closes")
