"""Migração de extrato Nubank -> ledger (STORY-01-13-14).

Carga histórica/bulk reusando o mesmo parser/serviço do endpoint. Idempotente
(dedup por external_id). Roda local antes de aplicar em produção (ADR / runbook).

Uso (a partir de api/):
    uv run python -m scripts.migrate_ledger <arquivo.ofx|.csv> <account_id> [--apply]

Sem --apply: dry-run (parse + classificação, sem gravar).
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
    classify,
    import_statement,
    parse_statement,
)


def _self_identifiers() -> list[str]:
    return [s.strip() for s in settings.ledger_self_identifiers.split(",") if s.strip()]


async def _apply(
    account_id: uuid.UUID, entries: Sequence[StatementEntry], self_ids: Sequence[str]
) -> ImportReport:
    await init_pool()
    try:
        async with get_pool().acquire() as conn:
            return await import_statement(conn, account_id, entries, self_ids)
    finally:
        await close_pool()


def main() -> None:
    raw_args = sys.argv[1:]
    apply = "--apply" in raw_args
    args = [a for a in raw_args if a != "--apply"]
    if len(args) != 2:
        print("uso: python -m scripts.migrate_ledger <arquivo> <account_id> [--apply]")
        return

    path = Path(args[0])
    account_id = uuid.UUID(args[1])
    entries = parse_statement(path.name, path.read_text(encoding="utf-8", errors="replace"))
    self_ids = _self_identifiers()

    kinds: Counter[str] = Counter(classify(e, self_ids).kind for e in entries)
    print(f"arquivo: {path.name}  entradas: {len(entries)}  classificação: {dict(kinds)}")

    if not apply:
        print("dry-run — use --apply para gravar")
        return

    report = asyncio.run(_apply(account_id, entries, self_ids))
    print(
        f"importadas: {report.imported}  duplicadas: {report.duplicates}  "
        f"puladas(invest/transf): {report.skipped}  erros: {report.errors}"
    )


if __name__ == "__main__":
    main()
