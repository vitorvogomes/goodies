"""Migração de extrato Nubank -> ledger (STORY-01-13-14).

Carga histórica/bulk reusando o mesmo parser/serviço do endpoint. Idempotente
(dedup por external_id). Roda local antes de aplicar em produção (ADR / runbook).

Uso (a partir de api/):
    uv run python -m scripts.migrate_ledger <arquivo.ofx|.csv> [account_id] [--apply]

OFX: a conta é resolvida pelo ACCTID do arquivo (account_id opcional).
CSV: informe o account_id. Sem --apply: dry-run (parse + classificação, sem gravar).
"""

import asyncio
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from config import settings
from db.connection import close_pool, get_pool, init_pool
from engines.ledger.importer import (
    ImportReport,
    StatementEntry,
    _load_rules,
    classify,
    import_statement,
    parse_account_number,
    parse_statement,
)


def _self_identifiers() -> list[str]:
    return [s.strip() for s in settings.ledger_self_identifiers.split(",") if s.strip()]


async def run(
    name: str,
    acctid: str | None,
    fallback: uuid.UUID | None,
    entries: Sequence[StatementEntry],
    self_ids: Sequence[str],
    apply: bool,
) -> None:
    await init_pool()
    try:
        async with get_pool().acquire() as conn:
            own = await conn.fetch(
                "SELECT account_number FROM accounts WHERE account_number IS NOT NULL"
            )
            identifiers = [r["account_number"] for r in own] + list(self_ids)
            rules = await _load_rules(conn)
            kinds: Counter[str] = Counter(classify(e, rules, identifiers).kind for e in entries)
            print(
                f"arquivo: {name}  conta(ACCTID): {acctid or '—'}  "
                f"entradas: {len(entries)}  classificação: {dict(kinds)}"
            )
            if not apply:
                print("dry-run — use --apply para gravar")
                return

            target = fallback
            if acctid:
                row = await conn.fetchrow(
                    "SELECT id FROM accounts WHERE account_number = $1", acctid
                )
                if row is None:
                    print(f"ERRO: conta com número {acctid} não cadastrada — crie-a antes.")
                    return
                target = row["id"]
            if target is None:
                print("ERRO: informe o account_id (arquivo sem número de conta).")
                return

            report: ImportReport = await import_statement(conn, target, entries, self_ids)
            print(
                f"importadas: {report.imported}  duplicadas: {report.duplicates}  "
                f"erros: {report.errors}"
            )
    finally:
        await close_pool()


def main() -> None:
    raw_args = sys.argv[1:]
    apply = "--apply" in raw_args
    args = [a for a in raw_args if a != "--apply"]
    if not (1 <= len(args) <= 2):
        print("uso: python -m scripts.migrate_ledger <arquivo> [account_id] [--apply]")
        return

    path = Path(args[0])
    fallback = uuid.UUID(args[1]) if len(args) == 2 else None
    content = path.read_text(encoding="utf-8", errors="replace")
    asyncio.run(
        run(
            path.name,
            parse_account_number(content),
            fallback,
            parse_statement(path.name, content),
            _self_identifiers(),
            apply,
        )
    )


if __name__ == "__main__":
    main()
