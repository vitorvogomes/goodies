"""WI-1 (pré-m3): reclassifica resgates de caixinha in-place (income → investment net).

Os resgates de caixinha hoje voltam como `income/Resgate`, inflando a receita e a
taxa de poupança (a Turbo girou ~R$24k de ida e volta = ~R$24k de "receita" que não
existe). Política caixinha=investment net: o resgate vira `investment` (valor
positivo), netando o total investido; a receita fica limpa.

In-place e IDEMPOTENTE (UPDATE por categoria; re-run = 0). NÃO é reset+reimport: os
dados de `transactions` são curados à mão e não são reproduzíveis pelo importador.
NÃO rode `reset_ledger` depois — apagaria a curadoria + este conserto.

Uso (a partir de api/):
    DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
      uv run python -m scripts.reclassify_caixinhas          # dry-run (mostra o efeito)
    DATABASE_URL=...localhost... uv run python -m scripts.reclassify_caixinhas --apply
"""

import asyncio
import sys
from urllib.parse import urlparse

import asyncpg

from config import settings
from db.connection import close_pool, get_pool, init_pool

# Categoria-destino (investimento) onde as duas pernas da caixinha convivem.
_INVEST_CATEGORY = "Caixinha/RDB Nubank"


def _rowcount(tag: str) -> int:
    """Extrai N de um command tag 'UPDATE N'."""
    return int(tag.split()[-1]) if tag else 0


async def reclassify_caixinhas(conn: asyncpg.Connection) -> dict[str, int]:
    """Aplica a reclassificação (idempotente). Retorna contagens.

    - apps_fixed: aplicações de caixinha que não estavam como investment (defesa).
    - resgates_moved: linhas income/Resgate movidas para investment/Caixinha-RDB.
    """
    apps = await conn.execute(
        "UPDATE transactions SET kind = 'investment' WHERE category = $1 AND kind <> 'investment'",
        _INVEST_CATEGORY,
    )
    resgates = await conn.execute(
        "UPDATE transactions SET kind = 'investment', category = $1 "
        "WHERE category = 'Resgate' AND kind <> 'investment'",
        _INVEST_CATEGORY,
    )
    return {"apps_fixed": _rowcount(apps), "resgates_moved": _rowcount(resgates)}


async def _preflight(conn: asyncpg.Connection) -> int:
    """Conta linhas com cara de caixinha FORA das categorias esperadas (deve ser 0)."""
    return int(
        await conn.fetchval(
            "SELECT count(*) FROM transactions "
            "WHERE category NOT IN ('Caixinha/RDB Nubank','Resgate') "
            "AND (description ILIKE 'Aplicação RDB%' OR description ILIKE 'Resgate RDB%' "
            "OR description ILIKE 'Aplicação Fundo - Nu Reserva%' "
            "OR description ILIKE 'Resgate Fundo - Nu Reserva%' "
            "OR description ILIKE 'Dinheiro guardado%')"
        )
    )


async def _print_summary(conn: asyncpg.Connection, label: str) -> None:
    print(f"\n=== monthly_summary ({label}) — últimos 6 meses ===")
    rows = await conn.fetch(
        "SELECT to_char(month,'YYYY-MM') m, total_income, savings_rate, total_invested "
        "FROM monthly_summary ORDER BY m DESC LIMIT 6"
    )
    for r in sorted(rows, key=lambda x: x["m"]):
        print(
            f"  {r['m']}  receita={float(r['total_income']):>9.2f}  "
            f"poupança(B)={float(r['savings_rate']):>6.2f}%  "
            f"investido={float(r['total_invested']):>9.2f}"
        )


async def run(apply: bool) -> None:
    u = urlparse(settings.database_url)
    print(f"banco alvo: {u.hostname}:{u.port}/{(u.path or '').lstrip('/')}")
    await init_pool(settings.database_url)
    try:
        async with get_pool().acquire() as conn:
            stray = await _preflight(conn)
            if stray:
                print(
                    f"⚠️  ATENÇÃO: {stray} linha(s) de caixinha fora das categorias "
                    "esperadas — revise antes de aplicar."
                )
            pending = int(
                await conn.fetchval(
                    "SELECT count(*) FROM transactions "
                    "WHERE category = 'Resgate' AND kind <> 'investment'"
                )
            )
            print(f"resgates a mover (income/Resgate → investment): {pending}")
            await _print_summary(conn, "antes")
            if not apply:
                print("\ndry-run — use --apply para gravar a reclassificação.")
                return
            async with conn.transaction():
                result = await reclassify_caixinhas(conn)
            print(
                f"\n✅ apps conferidas: {result['apps_fixed']}  | "
                f"resgates movidos: {result['resgates_moved']}"
            )
            await _print_summary(conn, "depois")
            bal = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transactions")
            print(f"\nsaldo acumulado (SUM de tudo, invariante): {float(bal):.2f}")
    finally:
        await close_pool()


def main() -> None:
    apply = "--apply" in sys.argv[1:] or "--yes" in sys.argv[1:]
    asyncio.run(run(apply))


if __name__ == "__main__":
    main()
