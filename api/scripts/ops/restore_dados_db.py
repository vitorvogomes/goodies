"""Restaura em `goodies_dados` a base dos testes `dados_reais` (Story 1.2).

Padrão: o backup pré-migração fixado em `tests/dados_reais/pinned_backup.txt` (o da revisão
sob teste). Os testes fazem restaura → mede → `alembic upgrade <rev>` → mede; este comando é o
equivalente manual.

Uso (a partir de api/):
    uv run python -m scripts.ops.restore_dados_db [--backup <arquivo.dump>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from config import settings
from workers.backup import DbTarget, pinned_dados_backup, restore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    source = args.backup or pinned_dados_backup()
    if source is None or not source.is_file():
        print("backup fixado não encontrado; use --backup <arquivo.dump>", file=sys.stderr)
        sys.exit(1)
    target = DbTarget.from_dsn(settings.database_url).with_database("goodies_dados")
    asyncio.run(restore(source, target.dsn()))
    print(f"goodies_dados restaurado de {source.name}")


if __name__ == "__main__":
    main()
