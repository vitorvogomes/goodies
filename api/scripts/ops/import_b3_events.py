"""Eventos corporativos das movimentações B3 já importadas (Story 7.9): bonificação (compra a custo
zero) e leilão de fração (venda da fração). O import antigo os descartava e a conciliação com o
consolidado B3 divergia. Só as linhas de evento passam pelo `import_b3_workbook` — reimportar o
arquivo inteiro dobraria as liquidações D+2 já cobertas pela negociação (P20). Idempotente (o hash
da operação); com backup antes.

Uso (a partir de api/):
    uv run python -m scripts.ops.import_b3_events --dry-run
    uv run python -m scripts.ops.import_b3_events [--dir ../files/b3/extrato]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

import asyncpg

from config import settings
from engines.common.owner import get_owner_id
from engines.portfolio.b3_import import is_corporate_event
from engines.portfolio.b3_import_service import import_b3_workbook
from engines.portfolio.b3_workbook import load_workbook_sheets
from workers.backup import make_pre_migration_backup

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "files" / "b3" / "extrato"
_SHEET = "Movimentação"


def movimentacoes(folder: Path) -> list[Path]:
    return sorted(folder.glob("movimentacao-*.xlsx"))


def event_sheets(path: Path) -> dict[str, list[tuple[Any, ...]]] | None:
    rows = load_workbook_sheets(path.read_bytes()).get(_SHEET) or []
    events = [r for r in rows[1:] if len(r) > 2 and r[2] and is_corporate_event(str(r[2]))]
    return {_SHEET: [rows[0], *events]} if events else None


async def import_events(dsn: str, folder: Path, *, dry_run: bool) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(dsn)
    out: list[dict[str, Any]] = []
    try:
        owner = await get_owner_id(conn)
        for path in await asyncio.to_thread(movimentacoes, folder):
            sheets = await asyncio.to_thread(event_sheets, path)
            if sheets is None:
                continue
            async with conn.transaction():
                report = await import_b3_workbook(conn, owner, sheets, dry_run=dry_run)
            out.append({"file": path.name, **report})
    finally:
        await conn.close()
    return out


async def _main(folder: Path, dry_run: bool) -> None:
    if not dry_run:
        await make_pre_migration_backup(settings.database_url, "pre-b3-eventos")
    for r in await import_events(settings.database_url, folder, dry_run=dry_run):
        verb = "a importar" if dry_run else "importados"
        print(f"{r['file']}: {r['imported']} {verb}, {r['skipped_duplicate']} já na base.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.dir, args.dry_run))


if __name__ == "__main__":
    main()
