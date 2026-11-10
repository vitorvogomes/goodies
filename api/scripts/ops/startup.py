"""Subida do container da api (Story 1.2 — AD-18).

1. Confere `BACKUP_DIR` (recusa pasta sincronizada com a nuvem ou dentro do repo).
2. `AUTO_MIGRATE=false` (padrão): banco fora do `head` → não sobe e manda rodar
   `scripts.ops.migrar`.
   `AUTO_MIGRATE=true`: backup → `alembic upgrade head`.
   Banco vazio com `AUTO_MIGRATE=true` (ADR-018): bootstrap `0001` → admin de
   `ADMIN_EMAIL`/`ADMIN_PASSWORD` → `head`.
3. Sobe o uvicorn **sem** `--reload` (este serviço aponta para o banco real), em
   `API_HOST`/`PORT` (o Railway injeta `PORT`).
"""

from __future__ import annotations

import asyncio
import os
import sys

from config import Settings, settings
from workers.backup import BackupDirError, backup_dir
from workers.dbops import admin_from_env, startup_gate


def uvicorn_argv(s: Settings) -> list[str]:
    return ["uvicorn", "main:app", "--host", s.api_host, "--port", str(s.port)]


def main() -> None:
    try:
        backup_dir()
    except BackupDirError as exc:
        print(f"api não sobe: {exc}", file=sys.stderr)
        sys.exit(1)
    decision = asyncio.run(
        startup_gate(
            settings.database_url, auto_migrate=settings.auto_migrate, admin=admin_from_env()
        )
    )
    if not decision.ok:
        print(f"api não sobe: {decision.message}", file=sys.stderr)
        sys.exit(1)
    print(f"startup: {decision.message}")
    argv = uvicorn_argv(settings)
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
