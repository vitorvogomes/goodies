"""Subida do container da api (Story 1.2 — AD-18).

1. Confere `BACKUP_DIR` (recusa pasta sincronizada com a nuvem ou dentro do repo).
2. `AUTO_MIGRATE=false` (padrão): banco fora do `head` → não sobe e manda rodar
   `scripts.ops.migrar`.
   `AUTO_MIGRATE=true`: backup → `alembic upgrade head`.
3. Sobe o uvicorn **sem** `--reload` (este serviço aponta para o banco real).
"""

from __future__ import annotations

import asyncio
import os
import sys

from config import settings
from workers.backup import BackupDirError, backup_dir
from workers.dbops import startup_gate


def main() -> None:
    try:
        backup_dir()
    except BackupDirError as exc:
        print(f"api não sobe: {exc}", file=sys.stderr)
        sys.exit(1)
    decision = asyncio.run(startup_gate(settings.database_url, auto_migrate=settings.auto_migrate))
    if not decision.ok:
        print(f"api não sobe: {decision.message}", file=sys.stderr)
        sys.exit(1)
    print(f"startup: {decision.message}")
    os.execvp("uvicorn", ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
