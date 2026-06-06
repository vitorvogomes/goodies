"""caixinha→investment (net) nas regras futuras de classificação

Revision ID: 0009_caixinha_classify_patterns
Revises: 0008_asset_prices
Create Date: 2026-06-06

Pré-m3 (coerência Nubank↔Portfólio). Decisão: caixinha = `investment` net — a
APLICAÇÃO e o RESGATE de caixinha são ambos `investment` (o resgate volta com
valor positivo e neta o total investido), p/ não inflar a receita com resgate.

Esta migration ajusta apenas as REGRAS de classificação FUTURA (categories.
match_patterns, lidas pelo importador). As LINHAS já gravadas e curadas à mão são
corrigidas in-place por `scripts/reclassify_caixinhas.py` (não por migration —
não são reproduzíveis e não devem virar histórico permanente).

Idempotente e defensiva (array_append/remove com guard; UPDATE WHERE name=... é
no-op onde a categoria não existe — ex.: bancos sem a curadoria do usuário).

- garante os anchors de caixinha (aplicação + resgate) na categoria de investimento
  `Caixinha/RDB Nubank` — p/ que 'Resgate Fundo - Nu Reserva Imediata...' caia em
  investment, não receita;
- neutraliza a categoria income `Resgate` (existe só no banco curado).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_caixinha_classify_patterns"
down_revision: str | None = "0008_asset_prices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Anchors de caixinha (aplicação + resgate) → categoria de investimento.
_CAIXINHA_ANCHORS = (
    "caixinha",
    "rdb",
    "aplicação rdb",
    "aplicacao rdb",
    "resgate rdb",
    "nu reserva imediata",
    "dinheiro guardado",
)


def _append_pattern(category: str, pattern: str) -> None:
    """array_append idempotente (guard anti-dup); no-op se a categoria não existe."""
    op.execute(
        "UPDATE categories "
        f"SET match_patterns = array_append(match_patterns, '{pattern}') "
        f"WHERE name = '{category}' AND NOT ('{pattern}' = ANY(match_patterns))"
    )


def _remove_pattern(category: str, pattern: str) -> None:
    op.execute(
        "UPDATE categories "
        f"SET match_patterns = array_remove(match_patterns, '{pattern}') "
        f"WHERE name = '{category}'"
    )


def upgrade() -> None:
    # Caixinha futura → investment (apps + resgates).
    for pat in _CAIXINHA_ANCHORS:
        _append_pattern("Caixinha/RDB Nubank", pat)
    # Neutraliza a categoria income 'Resgate' (só no banco curado): tira o pattern
    # 'resgate' (p/ não vencer o longest-match) e desativa. No-op onde não existe.
    op.execute(
        "UPDATE categories "
        "SET match_patterns = array_remove(match_patterns, 'resgate'), is_active = false "
        "WHERE name = 'Resgate' AND kind = 'income'"
    )


def downgrade() -> None:
    # Reverte os 4 anchors que o upgrade adicionou (os demais já vinham do seed 0006:
    # 'caixinha', 'rdb', 'dinheiro guardado' — mantidos intactos).
    for pat in ("aplicação rdb", "aplicacao rdb", "resgate rdb", "nu reserva imediata"):
        _remove_pattern("Caixinha/RDB Nubank", pat)
    # Reativa 'Resgate' income (se existir) e devolve o pattern 'resgate'.
    op.execute(
        "UPDATE categories "
        "SET match_patterns = array_append(match_patterns, 'resgate'), is_active = true "
        "WHERE name = 'Resgate' AND kind = 'income' "
        "AND NOT ('resgate' = ANY(match_patterns))"
    )
