"""Operações de esquema do banco local (Story 1.2 — AD-18).

- `head_revision` / `current_revision`: onde o código e o banco estão no Alembic.
- `alembic_upgrade`: roda o Alembic noutro processo contra um DSN explícito (o `env.py` aplica a
  guarda de backup quando o banco não é descartável).
- `migrar`: o único caminho que migra o banco real — branch `main` limpa, testes `dados_reais`
  verdes (nenhum pulado) e backup feito na hora; qualquer etapa falhando, não migra.
- `startup_gate`: decisão da subida do container (`AUTO_MIGRATE=false` → banco fora do `head`
  não sobe). Com `AUTO_MIGRATE=true` (produção, ADR-018), banco vazio faz o bootstrap
  `0002_refresh_token_hash` → admin → `head`: a 0016 exige um usuário e as sementes por usuário
  das migrações (grupos, categorias, regras, metas de classe) caem nele. Banco parado antes do
  admin (a 1ª subida caiu no meio) retoma o bootstrap.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import asyncpg
from alembic.config import Config
from alembic.script import ScriptDirectory

from auth.admin import upsert_admin
from workers.backup import REPO_ROOT, make_pre_migration_backup

API_DIR = Path(__file__).resolve().parents[1]
MIGRAR_HINT = "rode `python -m scripts.ops.migrar`"
# Banco vazio sobe até aqui, ganha o admin e só então vai ao head (a 0016 exige um usuário). A 0002
# traz `users.refresh_token_hash`, que o upsert do admin zera.
BOOTSTRAP_REVISION = "0002_refresh_token_hash"
# Onde uma 1ª subida que caiu antes do admin pode ter parado.
_BOOTSTRAP_RESUMABLE = (None, "0001_initial_users", BOOTSTRAP_REVISION)


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


@dataclass(frozen=True)
class AdminCredentials:
    email: str
    password: str

    def __repr__(self) -> str:  # nunca a senha em log/traceback
        return f"AdminCredentials(email={self.email!r}, password=***)"


def admin_from_env(env: Mapping[str, str] = os.environ) -> AdminCredentials | None:
    """`ADMIN_EMAIL`/`ADMIN_PASSWORD` do ambiente (só na 1ª subida); vazio conta como ausente."""
    email = env.get("ADMIN_EMAIL", "").strip()
    password = env.get("ADMIN_PASSWORD", "")
    if not email or not password.strip():
        return None
    return AdminCredentials(email, password)


async def _seed_admin(dsn: str, admin: AdminCredentials) -> None:
    await upsert_admin(dsn, admin.email, admin.password)


async def startup_gate(
    dsn: str,
    *,
    auto_migrate: bool,
    upgrade: Callable[[str, str], None] = alembic_upgrade,
    admin: AdminCredentials | None = None,
    seed_admin: Callable[[str, AdminCredentials], Awaitable[None]] = _seed_admin,
) -> StartupDecision:
    head = head_revision()
    current = await current_revision(dsn)
    if current == head:
        return StartupDecision(True, f"banco no head ({head})")
    if not auto_migrate:
        return StartupDecision(
            False, f"banco em {current or 'vazio'}, código em {head}: {MIGRAR_HINT}"
        )
    if current in _BOOTSTRAP_RESUMABLE:
        if admin is None:
            return StartupDecision(
                False,
                f"banco {'vazio' if current is None else 'parado na ' + current}: defina "
                "ADMIN_EMAIL e ADMIN_PASSWORD para o bootstrap (só lidos com banco vazio)",
            )
        await make_pre_migration_backup(dsn, f"pre-{head}")
        upgrade(dsn, BOOTSTRAP_REVISION)
        await seed_admin(dsn, admin)
        upgrade(dsn, "head")
        return StartupDecision(True, f"bootstrap: banco vazio → admin → {head}, com backup antes")
    await make_pre_migration_backup(dsn, f"pre-{head}")
    upgrade(dsn, "head")
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
