"""Registra a DEVOLUÇÃO (caixa de volta ao Nubank) da venda real do Tesouro que não foi
importada no extrato.

Problema (forense 2026-06-10): o trilho Tesouro fica com resíduo de R$145,94 (saiu 3.168,66
vs virou posição 3.022,72). A decomposição: R$114,59 = a ÚNICA venda real (Tesouro IPCA+ com
Juros Semestrais 2055, 2025-02-24) cuja devolução de caixa NUNCA entrou no ledger Nubank —
some no `asset_operations` (venda) mas o dinheiro de volta não aparece como inflow. O restante
(~R$31,35) é artefato consolidado-vs-transferência (taxas) nas 40 compras, irredutível.

Correção: insere 1 transação de inflow `+114,59` (kind=investment, category=Tesouro Direto
Nubank) na data da venda → reduz `saiu` em 114,59 → resíduo do Tesouro cai de 145,94 p/ ~31,35.
O valor e a data vêm da PRÓPRIA op de venda (não hardcoded). Idempotente por external_id.

ATENÇÃO — toca o ledger curado: sobe a "Saldo Acumulado" em +114,59 (a venda devolveu caixa
real que não estava registrado). NÃO altera a taxa de poupança (inflow é `investment`, não
poupança). Só rodar --apply após confirmar que os proventos da venda voltaram ao Nubank (e não
ficaram parados no caixa do Tesouro). Dry-run por padrão.

Reverter:
  DELETE FROM transactions WHERE external_id = 'tesouro-sale-return:2055';

Uso (a partir de api/):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python -m scripts.register_tesouro_sale_return            # dry-run
    DATABASE_URL=...localhost... uv run python -m scripts.register_tesouro_sale_return --apply
"""

import asyncio
import sys
from typing import Any
from urllib.parse import urlparse

import asyncpg

from config import settings
from db.connection import close_pool, get_pool, init_pool

_MARKER = "tesouro-sale-return:2055"
_LEDGER_CATEGORY = "Tesouro Direto Nubank"
_ASSET_CATEGORY = "Aposentadoria"


async def register_tesouro_sale_return(
    conn: asyncpg.Connection, *, apply: bool
) -> dict[str, Any]:
    """Insere a devolução de caixa da venda real do Tesouro (idempotente)."""
    if await conn.fetchval(
        "SELECT 1 FROM transactions WHERE external_id = $1", _MARKER
    ):
        return {"status": "already_done"}
    # a venda real do Tesouro: derivar valor + data da própria op (não hardcoded).
    venda = await conn.fetchrow(
        "SELECT asset_symbol, ROUND((quantidade * valor_unitario)::numeric, 2) AS total, "
        "data_operacao FROM asset_operations "
        "WHERE asset_category = $1 AND tipo = 'venda' ORDER BY data_operacao",
        _ASSET_CATEGORY,
    )
    if venda is None:
        return {"status": "noop", "reason": "nenhuma venda no Tesouro"}
    amount = float(venda["total"])
    # reaproveita a conta que já lança as transações do Tesouro (não fabrica conta nova).
    account_id = await conn.fetchval(
        "SELECT account_id FROM transactions "
        "WHERE kind = 'investment' AND category = $1 AND account_id IS NOT NULL "
        "GROUP BY account_id ORDER BY COUNT(*) DESC LIMIT 1",
        _LEDGER_CATEGORY,
    )
    if account_id is None:
        return {"status": "noop", "reason": "sem conta de transações do Tesouro"}
    out = {
        "status": "applied" if apply else "dry-run",
        "asset": venda["asset_symbol"],
        "amount": amount,
        "date": venda["data_operacao"],
        "account_id": str(account_id),
    }
    if apply:
        await conn.execute(
            "INSERT INTO transactions (account_id, date, amount, category, kind, "
            "description, external_id) VALUES ($1, $2, $3, $4, 'investment', $5, $6)",
            account_id, venda["data_operacao"], amount, _LEDGER_CATEGORY,
            f"Devolução - venda {venda['asset_symbol']} (caixa de volta ao Nubank)",
            _MARKER,
        )
    return out


async def run(apply: bool) -> None:
    u = urlparse(settings.database_url)
    print(f"banco alvo: {u.hostname}:{u.port}/{(u.path or '').lstrip('/')}")
    await init_pool(settings.database_url)
    try:
        async with get_pool().acquire() as conn:
            if apply:
                async with conn.transaction():
                    res = await register_tesouro_sale_return(conn, apply=True)
            else:
                res = await register_tesouro_sale_return(conn, apply=False)
    finally:
        await close_pool()
    print(f"\nTesouro sale-return: {res}")
    if res.get("status") in ("dry-run", "applied"):
        print(
            f"  resíduo Tesouro esperado: 145,94 -> "
            f"{round(145.94 - float(res['amount']), 2):.2f}"
        )
    if not apply:
        print("\ndry-run — use --apply para gravar (toca o ledger; ver docstring).")


def main() -> None:
    apply = "--apply" in sys.argv[1:] or "--yes" in sys.argv[1:]
    asyncio.run(run(apply))


if __name__ == "__main__":
    main()
