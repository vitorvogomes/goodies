"""Reset + reimport do ledger (kind-aware).

Apaga TODAS as transações e reimporta os OFX/CSV de `files/nubank/` com a
classificação atual (coluna `kind` + `categories.match_patterns` + os
`LEDGER_SELF_IDENTIFIERS` do `.env`). Necessário quando os identificadores mudam,
pois o dedup por `external_id` NÃO reclassifica linhas já gravadas.

Uso (a partir de api/):
    uv run python -m scripts.reset_ledger          # dry-run (só mostra o alvo)
    uv run python -m scripts.reset_ledger --yes     # apaga e reimporta

OFX é roteado pelo ACCTID do arquivo para a conta cadastrada (account_number).
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.ledger.importer import import_statement, parse_account_number, parse_statement

_FILES_DIR = Path(__file__).resolve().parents[2] / "files" / "nubank"


def _self_identifiers() -> list[str]:
    return [s.strip() for s in settings.ledger_self_identifiers.split(",") if s.strip()]


async def run(apply: bool) -> None:
    u = urlparse(settings.database_url)
    self_ids = _self_identifiers()
    print(
        f"banco alvo: {u.hostname}:{u.port}/{(u.path or '').lstrip('/')}  "
        f"| self_identifiers: {len(self_ids)} itens  | arquivos: {_FILES_DIR}"
    )
    if not apply:
        print("dry-run — use --yes para APAGAR todas as transações e reimportar")
        return

    await init_pool()
    try:
        async with get_pool().acquire() as conn:
            deleted = await conn.execute("DELETE FROM transactions")
            print(f"{deleted}")
            files = sorted(_FILES_DIR.glob("*.ofx")) + sorted(_FILES_DIR.glob("*.csv"))
            if not files:
                print(f"ERRO: nenhum arquivo em {_FILES_DIR}")
                return

            total: Counter[str] = Counter()
            for f in files:
                content = f.read_text(encoding="utf-8", errors="replace")
                acctid = parse_account_number(content)
                row = (
                    await conn.fetchrow(
                        "SELECT id FROM accounts WHERE account_number = $1", acctid
                    )
                    if acctid
                    else None
                )
                if row is None:
                    print(f"  PULADO {f.name}: ACCTID {acctid or '—'} sem conta cadastrada")
                    continue
                entries = parse_statement(f.name, content)
                report = await import_statement(conn, row["id"], entries, self_ids)
                total["imported"] += report.imported
                total["duplicates"] += report.duplicates
                total["errors"] += report.errors
                print(f"  {f.name}: +{report.imported} (dup {report.duplicates})")

            print(f"\ntotal importado: {total['imported']}  duplicadas: {total['duplicates']}")
            print("\n=== monthly_summary (poupança B / investimento A) ===")
            rows = await conn.fetch(
                "SELECT to_char(month,'YYYY-MM') m, total_income, total_expense, "
                "savings_rate, total_invested, investment_rate FROM monthly_summary ORDER BY m"
            )
            for r in rows:
                print(
                    f"  {r['m']}  receita={float(r['total_income']):>9.2f}  "
                    f"consumo={float(r['total_expense']):>9.2f}  "
                    f"poupança(B)={float(r['savings_rate']):>6.2f}%  "
                    f"investido={float(r['total_invested']):>8.2f}  "
                    f"inv(A)={float(r['investment_rate']):>6.2f}%"
                )
            bal = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM transactions")
            print(f"\nsaldo acumulado real (SUM de tudo): {float(bal):.2f}")
    finally:
        await close_pool()


def main() -> None:
    asyncio.run(run("--yes" in sys.argv[1:]))


if __name__ == "__main__":
    main()
