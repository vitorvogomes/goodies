"""Operações de esquema do banco local (Story 1.2 — AD-18).

- `head_revision` / `current_revision`: onde o código e o banco estão no Alembic.
- `alembic_upgrade`: roda o Alembic noutro processo contra um DSN explícito (o `env.py` aplica a
  guarda de backup quando o banco não é descartável).
- `migrar`: o único caminho que migra o banco real — branch `main` limpa, testes `dados_reais`
  verdes (nenhum pulado) e backup feito na hora; qualquer etapa falhando, não migra.
- `startup_gate`: decisão da subida do container (`AUTO_MIGRATE=false` → banco fora do `head`
  não sobe).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import asyncpg
from alembic.config import Config
from alembic.script import ScriptDirectory

from workers.backup import REPO_ROOT, make_pre_migration_backup

API_DIR = Path(__file__).resolve().parents[1]
MIGRAR_HINT = "rode `python -m scripts.ops.migrar`"


class MigrationRefused(RuntimeError):
    """Uma pré-condição da migração do banco real falhou."""


def head_revision() -> str:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "db" / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if head is None:
        raise RuntimeError("sem revisões Alembic")
    return head


async def current_revision(dsn: str) -> str | None:
    conn = await asyncpg.connect(dsn)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        if not exists:
            return None
        value: str | None = await conn.fetchval("SELECT version_num FROM alembic_version")
        return value
    finally:
        await conn.close()


def alembic_upgrade(dsn: str, target: str = "head") -> None:
    env = {**os.environ, "DATABASE_URL": dsn}
    subprocess.run(["alembic", "upgrade", target], cwd=API_DIR, env=env, check=True)


@dataclass(frozen=True)
class StartupDecision:
    ok: bool
    message: str


async def startup_gate(
    dsn: str, *, auto_migrate: bool, upgrade: Callable[[str], None] | None = None
) -> StartupDecision:
    head = head_revision()
    current = await current_revision(dsn)
    if current == head:
        return StartupDecision(True, f"banco no head ({head})")
    if not auto_migrate:
        return StartupDecision(
            False, f"banco em {current or 'vazio'}, código em {head}: {MIGRAR_HINT}"
        )
    await make_pre_migration_backup(dsn, f"pre-{head}")
    (upgrade or alembic_upgrade)(dsn)
    return StartupDecision(True, f"migrado para {head} com backup antes")


# ---------------------------------------------------------------- migrar


def git_main_clean(repo: Path = REPO_ROOT) -> None:
    branch = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if branch != "main":
        raise MigrationRefused(
            f"branch atual é {branch or 'HEAD destacado'}; o banco real só migra a partir da main"
        )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        raise MigrationRefused("a main tem mudanças não commitadas; commite antes de migrar")


def dados_reais_green() -> None:
    env = {**os.environ, "DADOS_REAIS_REQUIRED": "1"}
    result = subprocess.run(
        ["uv", "run", "pytest", "-m", "dados_reais", "-rs", "-p", "no:cacheprovider"],
        cwd=API_DIR,
        env=env,
        check=False,
    )
    if result.returncode == 5:
        raise MigrationRefused("nenhum teste dados_reais encontrado")
    if result.returncode != 0:
        raise MigrationRefused("testes dados_reais falharam ou foram pulados")


async def migrar(
    dsn: str,
    target: str = "head",
    *,
    check_git: Callable[[], None] = git_main_clean,
    check_tests: Callable[[], None] = dados_reais_green,
    backup: Callable[[str, str], Awaitable[Path]] | None = None,
    upgrade: Callable[[str, str], None] = alembic_upgrade,
) -> Path:
    """Migra o banco real. Devolve o backup feito na hora. Qualquer falha → nada migra."""
    check_git()
    check_tests()
    make_backup = backup or make_pre_migration_backup
    try:
        taken = await make_backup(dsn, f"pre-{target}")
    except Exception as exc:
        raise MigrationRefused(f"backup falhou ({exc}); não migro") from exc
    upgrade(dsn, target)
    return taken
