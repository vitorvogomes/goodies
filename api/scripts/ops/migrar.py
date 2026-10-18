"""Migra o banco real (Story 1.2 — AD-18). Único caminho de migração do banco real.

Exige: branch `main` limpa, testes `dados_reais` verdes e nenhum pulado, e um backup feito na hora.
Qualquer etapa falhando, o banco não é tocado.

Uso (a partir de api/):
    uv run python -m scripts.ops.migrar [--alvo head]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from config import settings
from workers.dbops import MigrationRefused, current_revision, migrar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alvo", default="head")
    args = parser.parse_args()
    try:
        taken = asyncio.run(migrar(settings.database_url, args.alvo))
    except MigrationRefused as exc:
        print(f"migração recusada: {exc}", file=sys.stderr)
        sys.exit(1)
    rev = asyncio.run(current_revision(settings.database_url))
    print(f"banco em {rev}; backup antes da migração: {taken}")


if __name__ == "__main__":
    main()
