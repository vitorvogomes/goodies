"""Registra o rendimento REALIZADO das caixinhas Nubank (juros embutidos nos resgates).

Problema: o extrato Nubank lança o resgate inteiro (principal + juros) como saída de
principal, então `net = aportes - resgates` subconta o principal de caixinhas muito
giradas e o rendimento fica oculto. Ex.: Turbo gira ~R$24k de ida/volta → net R$2.276
quando o principal real é R$2.400 (a diferença = juros já sacados).

Correção (XIRR-NEUTRA — reclassifica resgate→juros, o caixa do dia não muda):
- **Turbo (aberta):** reduz o MAIOR resgate em R = principal_real - net e cria 1 op
  `juros` de R. `net_quantity` sobe p/ o principal real; o rendimento aparece em /income;
  o preço é recalibrado p/ preservar o valor atual exibido (o usuário ajusta o bruto inline).
- **Encerradas (fechadas, principal 0):** cria o ativo-bucket `Nubank-Encerradas` com 1 op
  `juros` = (resgates - aportes) das caixinhas encerradas, casadas por EXCLUSÃO de
  snow/turbo/guanabara (evita a ambiguidade de nomes: Extra/Reserva/HotCash/Potencial/
  Resp.Ltda vão todas p/ o mesmo bucket — o total é exato). Sem posição (net 0), só income.

IDEMPOTENTE (external_id marcador — re-run não duplica). Dry-run por padrão; --apply grava.

Reverter (se preciso):
  DELETE FROM asset_operations WHERE external_id IN
    ('caixinha-yield:Nubank-Turbo','caixinha-yield:Nubank-Encerradas');
  -- e somar de volta R$123,91 ao resgate do Turbo (ver `notes` da op de juros).

Uso (a partir de api/):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python -m scripts.oneoff.register_caixinha_yields           # dry-run
    DATABASE_URL=...localhost... uv run python -m scripts.oneoff.register_caixinha_yields --apply
"""

import asyncio
import sys
from datetime import date
from typing import Any
from urllib.parse import urlparse

import asyncpg

from config import settings
from db.connection import close_pool, get_pool, init_pool

# Principal REAL das caixinhas abertas com juros sacados embutidos (do relatório Nubank).
TURBO_PRINCIPAL = 2400.0

_TURBO_SYMBOL = "Nubank-Turbo"
_TURBO_MARKER = "caixinha-yield:Nubank-Turbo"
_CLOSED_SYMBOL = "Nubank-Encerradas"
_CLOSED_MARKER = "caixinha-yield:Nubank-Encerradas"
_CATEGORY = "Renda Fixa"
_BROKER = "Nubank"
_RF_LEDGER_CATEGORIES = ("Caixinha/RDB Nubank", "Renda Fixa Nubank")

_NET_QTY_SQL = (
    "SELECT COALESCE(SUM(CASE WHEN tipo IN ('compra','aporte') THEN quantidade "
    "WHEN tipo IN ('venda','resgate') THEN -quantidade ELSE 0 END), 0) "
    "FROM asset_operations WHERE asset_symbol = $1"
)


async def _user_id(conn: asyncpg.Connection) -> Any:
    return await conn.fetchval("SELECT id FROM users ORDER BY created_at LIMIT 1")


async def _insert_juros(
    conn: asyncpg.Connection,
    symbol: str,
    qty: float,
    data_operacao: date,
    external_id: str,
    notes: str,
) -> None:
    await conn.execute(
        "INSERT INTO asset_operations (user_id, broker, asset_symbol, asset_category, "
        "tipo, quantidade, valor_unitario, data_operacao, external_id, notes) "
        "VALUES ($1, $2, $3, $4, 'juros', $5, 1.0, $6, $7, $8)",
        await _user_id(conn), _BROKER, symbol, _CATEGORY,
        qty, data_operacao, external_id, notes,
    )


async def register_turbo_yield(
    conn: asyncpg.Connection, *, target_principal: float, apply: bool
) -> dict[str, Any]:
    """Reclassifica os juros sacados do Turbo: reduz o maior resgate e cria op `juros`."""
    if await conn.fetchval(
        "SELECT 1 FROM asset_operations WHERE external_id = $1", _TURBO_MARKER
    ):
        return {"status": "already_done"}
    net = float(await conn.fetchval(_NET_QTY_SQL, _TURBO_SYMBOL))
    realized = round(target_principal - net, 2)
    if realized <= 0:
        return {"status": "noop", "net": net, "realized": realized}
    biggest = await conn.fetchrow(
        "SELECT id, quantidade, data_operacao FROM asset_operations "
        "WHERE asset_symbol = $1 AND tipo = 'resgate' ORDER BY quantidade DESC LIMIT 1",
        _TURBO_SYMBOL,
    )
    if biggest is None or float(biggest["quantidade"]) <= realized:
        raise RuntimeError("resgate insuficiente p/ reclassificar o juros do Turbo")
    old_q = float(biggest["quantidade"])
    new_q = round(old_q - realized, 2)
    # preço recalibrado p/ preservar o valor atual exibido (não inflar com o +principal)
    price_row = await conn.fetchrow(
        "SELECT price_brl FROM asset_prices WHERE ticker = $1", _TURBO_SYMBOL
    )
    old_price = float(price_row["price_brl"]) if price_row else 1.0
    new_price = round(net * old_price / target_principal, 6)
    out = {
        "status": "applied" if apply else "dry-run",
        "net": net,
        "realized": realized,
        "resgate_id": str(biggest["id"]),
        "resgate_old_q": old_q,
        "resgate_new_q": new_q,
        "price_old": old_price,
        "price_new": new_price,
    }
    if apply:
        await conn.execute(
            "UPDATE asset_operations SET quantidade = $1 WHERE id = $2",
            new_q, biggest["id"],
        )
        await _insert_juros(
            conn, _TURBO_SYMBOL, realized, biggest["data_operacao"], _TURBO_MARKER,
            f"juros realizado reclassificado do resgate {biggest['id']}: -{realized:.2f}; "
            f"principal {net:.2f}->{target_principal:.2f}",
        )
        await conn.execute(
            "UPDATE asset_prices SET price_brl = $1 WHERE ticker = $2",
            new_price, _TURBO_SYMBOL,
        )
    return out


async def register_closed_yield(
    conn: asyncpg.Connection, *, apply: bool
) -> dict[str, Any]:
    """Registra o rendimento realizado das caixinhas encerradas num bucket (juros only)."""
    if await conn.fetchval(
        "SELECT 1 FROM asset_operations WHERE external_id = $1", _CLOSED_MARKER
    ):
        return {"status": "already_done"}
    row = await conn.fetchrow(
        "SELECT COALESCE(-SUM(amount), 0) AS net_saiu, MAX(date) AS last_date "
        "FROM transactions WHERE kind = 'investment' AND category = ANY($1::text[]) "
        "AND description NOT ILIKE '%snow%' AND description NOT ILIKE '%turbo%' "
        "AND description NOT ILIKE '%guanabara%'",
        list(_RF_LEDGER_CATEGORIES),
    )
    realized = round(-float(row["net_saiu"]), 2)  # net_saiu<0 (resgatou mais) -> juros>0
    last_date = row["last_date"]
    if realized <= 0 or last_date is None:
        return {"status": "noop", "realized": realized}
    out = {
        "status": "applied" if apply else "dry-run",
        "realized": realized,
        "last_date": last_date,
    }
    if apply:
        await _insert_juros(
            conn, _CLOSED_SYMBOL, realized, last_date, _CLOSED_MARKER,
            "rendimento realizado das caixinhas encerradas "
            "(Extra/Reserva/HotCash/Potencial), casadas por exclusao de snow/turbo/guanabara",
        )
    return out


async def run(apply: bool) -> None:
    u = urlparse(settings.database_url)
    print(f"banco alvo: {u.hostname}:{u.port}/{(u.path or '').lstrip('/')}")
    await init_pool(settings.database_url)
    try:
        async with get_pool().acquire() as conn:
            # apply=True envolve numa transação (atômico); dry-run não escreve nada.
            if apply:
                async with conn.transaction():
                    turbo = await register_turbo_yield(
                        conn, target_principal=TURBO_PRINCIPAL, apply=True
                    )
                    closed = await register_closed_yield(conn, apply=True)
            else:
                turbo = await register_turbo_yield(
                    conn, target_principal=TURBO_PRINCIPAL, apply=False
                )
                closed = await register_closed_yield(conn, apply=False)
    finally:
        await close_pool()
    print(f"\nTurbo:      {turbo}")
    print(f"Encerradas: {closed}")
    if not apply:
        print("\ndry-run — use --apply para gravar.")


def main() -> None:
    apply = "--apply" in sys.argv[1:] or "--yes" in sys.argv[1:]
    asyncio.run(run(apply))


if __name__ == "__main__":
    main()
