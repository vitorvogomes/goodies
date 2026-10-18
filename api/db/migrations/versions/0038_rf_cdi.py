"""Caixinhas e CDB valorados pelo CDI real (Story 7.4)

Revision ID: 0038_rf_cdi
Revises: 0037_summary_month_return
Create Date: 2026-10-18

Cadastra no ativo o %CDI que antes vivia no código (`caixinhas.CAIXINHAS`/`CDB_GUANABARA`):
`valuation = 'cdi'` e `pct_cdi` — Snow Trip e Reserva 100%, Turbo 115%, CDB Guanabara 117,5%. O
preço desses ativos deixa de ser manual: o job `rf_cdi` recalcula pelo CDI publicado.
A caixinha "Encerradas" (posição zerada) fica como está. Idempotente.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0038_rf_cdi"
down_revision: str | None = "0037_summary_month_return"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PCT = {
    "caixinha:snowtrip": "100",
    "caixinha:turbo": "115",
    "caixinha:reserva": "100",
    "cdb:guanabara": "117.5",
}


def upgrade() -> None:
    for key, pct in PCT.items():
        op.execute(
            f"UPDATE assets SET valuation = 'cdi', pct_cdi = {pct} WHERE key = '{key}'"
        )
    op.execute(
        "UPDATE asset_prices p SET is_manual = false, source = 'cdi' FROM assets a "
        "WHERE a.valuation = 'cdi' AND p.ticker = a.price_ref"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE asset_prices p SET is_manual = true, source = 'nubank-cdi' FROM assets a "
        "WHERE a.valuation = 'cdi' AND p.ticker = a.price_ref"
    )
    op.execute("UPDATE assets SET valuation = 'manual', pct_cdi = NULL WHERE valuation = 'cdi'")
