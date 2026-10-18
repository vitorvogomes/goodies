"""Restaura o backup mais recente do banco real em `goodies_dev` (Story 1.2).

`goodies_dev` é descartável: recriado do zero a cada execução.

Uso (a partir de api/):
    uv run python -m scripts.ops.restore_dev_db [--backup <arquivo.dump>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from config import settings
from workers.backup import DbTarget, latest_backup, restore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    real = DbTarget.from_dsn(settings.database_url)
    source = args.backup or latest_backup(real.database)
    if source is None:
        print("nenhum backup encontrado em BACKUP_DIR", file=sys.stderr)
        sys.exit(1)
    asyncio.run(restore(source, real.with_database("goodies_dev").dsn()))
    print(f"goodies_dev restaurado de {source.name}")


if __name__ == "__main__":
    main()
