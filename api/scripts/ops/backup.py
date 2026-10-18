"""Backup manual do banco (Story 1.2). Vai para `<BACKUP_DIR>/pre-migracao/`, fora da retenção.

Uso (a partir de api/):
    uv run python -m scripts.ops.backup [--tag pre-0016]
"""

from __future__ import annotations

import argparse
import asyncio

from config import settings
from workers.backup import make_pre_migration_backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="manual")
    args = parser.parse_args()
    dest = asyncio.run(make_pre_migration_backup(settings.database_url, args.tag))
    print(f"backup gravado: {dest}")


if __name__ == "__main__":
    main()
