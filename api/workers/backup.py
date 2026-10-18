"""Backup do banco local (Story 1.2 — AD-18, ADR-014).

O banco local é a única cópia dos dados. Este módulo concentra:
- regras puras: nome do arquivo, retenção por idade (30 diários + 12 mensais), diretório recusado
  (dentro do repo ou em pasta sincronizada com a nuvem), bancos descartáveis;
- execução de `pg_dump`/`pg_restore`: binários locais (dentro do container, cliente 15 da imagem) ou
  `docker compose exec postgres` (no host, para usar o cliente 15 do próprio servidor);
- o job diário `db_backup`, o job mensal `restore_check` e a guarda `ensure_recent_backup`, usada
  antes de toda escrita de dado fora da subida do container (Alembic, close_retro, refechar,
  rederivações).

Backups pré-migração ficam em `<BACKUP_DIR>/pre-migracao/` e a retenção nunca os apaga.
Nada aqui loga DSN, senha ou valor financeiro.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import asyncpg
import structlog

from config import settings

logger = structlog.get_logger()

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_MIGRATION_SUBDIR = "pre-migracao"
DAILY_KEEP_DAYS = 30
MONTHLY_KEEP = 12
RECENT_BACKUP_MAX_AGE = timedelta(hours=1)

# Trechos de caminho de pastas sincronizadas com a nuvem (comparação sem caixa e sem espaços).
_CLOUD_MARKERS = ("onedrive", "dropbox", "googledrive", "mydrive", "meudrive", "icloud")
_DISPOSABLE_DBS = frozenset({"goodies_test", "goodies_dados", "goodies_dev"})
_DISPOSABLE_PREFIXES = ("goodies_tmp_", "goodies_restore_")
_NAME_RE = re.compile(
    r"^(?P<db>[a-z0-9_]+?)_(?P<ts>\d{8}_\d{6})(?:_(?P<tag>[A-Za-z0-9._-]+))?\.dump$"
)


class BackupDirError(RuntimeError):
    """BACKUP_DIR ausente ou num lugar proibido."""


class BackupError(RuntimeError):
    """pg_dump/pg_restore falhou."""


# ---------------------------------------------------------------- regras puras


def backup_name(db: str, moment: datetime, tag: str | None = None) -> str:
    stamp = moment.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{db}_{stamp}{'_' + tag if tag else ''}.dump"


def parse_backup_moment(name: str) -> datetime | None:
    match = _NAME_RE.match(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match["ts"], "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _backup_db(name: str) -> str | None:
    match = _NAME_RE.match(name)
    return match["db"] if match else None


def _months_between(older: date, newer: date) -> int:
    return (newer.year - older.year) * 12 + newer.month - older.month


def retention_to_delete(names: Sequence[str], today: date) -> list[str]:
    """Arquivos da pasta diária que saem: ficam os de até 30 dias e o mais novo de cada um dos
    12 meses anteriores ao atual. Arquivo de nome desconhecido nunca sai."""
    dated = [(n, m) for n in names if (m := parse_backup_moment(n)) is not None]
    newest_per_month: dict[tuple[int, int], tuple[str, datetime]] = {}
    for name, moment in dated:
        key = (moment.year, moment.month)
        if key not in newest_per_month or moment > newest_per_month[key][1]:
            newest_per_month[key] = (name, moment)
    keep_monthly = {
        name
        for name, moment in newest_per_month.values()
        if _months_between(moment.date(), today) <= MONTHLY_KEEP
    }
    return [
        name
        for name, moment in dated
        if (today - moment.date()).days > DAILY_KEEP_DAYS and name not in keep_monthly
    ]


def validate_backup_dir(raw: str, *, repo_root: Path = REPO_ROOT) -> Path:
    if not raw.strip():
        raise BackupDirError("BACKUP_DIR não configurado no .env")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise BackupDirError("BACKUP_DIR precisa ser um caminho absoluto, fora do repositório")
    squashed = str(path).lower().replace(" ", "").replace("-", "")
    if any(marker in squashed for marker in _CLOUD_MARKERS):
        raise BackupDirError(
            "BACKUP_DIR está numa pasta sincronizada com a nuvem; use um disco local"
        )
    resolved = path.resolve()
    root = repo_root.resolve()
    # Dentro do container não há repositório (o código é a imagem): só vale a checagem de nuvem.
    in_repo = (root / ".git").exists() and (resolved == root or root in resolved.parents)
    if in_repo:
        raise BackupDirError("BACKUP_DIR está dentro do repositório; use um diretório fora dele")
    return path


def is_disposable_db(name: str) -> bool:
    return name in _DISPOSABLE_DBS or name.startswith(_DISPOSABLE_PREFIXES)


# ---------------------------------------------------------------- DSN e ferramentas


@dataclass(frozen=True)
class DbTarget:
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_dsn(cls, dsn: str) -> DbTarget:
        url = urlparse(dsn)
        return cls(
            host=url.hostname or "localhost",
            port=url.port or 5432,
            user=unquote(url.username or "postgres"),
            password=unquote(url.password or ""),
            database=(url.path or "/postgres").lstrip("/") or "postgres",
        )

    def with_database(self, database: str) -> DbTarget:
        return DbTarget(self.host, self.port, self.user, self.password, database)

    def dsn(self) -> str:
        user, password = quote(self.user, safe=""), quote(self.password, safe="")
        auth = f"{user}:{password}@" if self.password else f"{user}@"
        return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"


def _tool_cmd(tool: str, target: DbTarget, args: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    """Comando + env do `pg_dump`/`pg_restore`. A senha vai por PGPASSWORD, nunca no argv."""
    env = dict(os.environ)
    if settings.pg_tools == "local":
        env["PGPASSWORD"] = target.password
        conn = ["-h", target.host, "-p", str(target.port), "-U", target.user]
        return [tool, *conn, *args], env
    compose = ["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.yml")]
    # Socket local do container do Postgres (trust): dispensa a senha.
    return [*compose, "exec", "-T", "postgres", tool, "-U", target.user, *args], env


async def _run(
    cmd: list[str], env: dict[str, str], *, stdin: Path | None = None, stdout: Path | None = None
) -> None:
    in_f = stdin.open("rb") if stdin else None
    out_f = stdout.open("wb") if stdout else None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=in_f or asyncio.subprocess.DEVNULL,
            stdout=out_f or asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, err = await proc.communicate()
    finally:
        for f in (in_f, out_f):
            if f is not None:
                f.close()
    if proc.returncode != 0:
        tail = err.decode(errors="replace").strip().splitlines()[-1:] or ["sem saída"]
        raise BackupError(
            f"{cmd[0] if cmd[0] != 'docker' else 'docker ' + cmd[-1]} falhou: {tail[0]}"
        )


async def dump(dsn: str, dest: Path) -> Path:
    """`pg_dump -Fc` do banco do DSN em `dest` (grava em .tmp e renomeia: nunca deixa arquivo pela
    metade com nome válido)."""
    target = DbTarget.from_dsn(dsn)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    cmd, env = _tool_cmd("pg_dump", target, ["-Fc", "-d", target.database])
    try:
        await _run(cmd, env, stdout=tmp)
        if tmp.stat().st_size == 0:
            raise BackupError("pg_dump gerou arquivo vazio")
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


async def recreate_database(target: DbTarget) -> None:
    if not is_disposable_db(target.database):
        raise BackupError(f"recusado recriar {target.database}: só bancos descartáveis")
    conn = await asyncpg.connect(target.with_database("postgres").dsn())
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            target.database,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{target.database}"')
        await conn.execute(f'CREATE DATABASE "{target.database}"')
    finally:
        await conn.close()


async def restore(backup: Path, target_dsn: str) -> None:
    """Restaura `backup` num banco **descartável**, recriado do zero."""
    target = DbTarget.from_dsn(target_dsn)
    await recreate_database(target)
    cmd, env = _tool_cmd(
        "pg_restore", target, ["--no-owner", "--no-privileges", "-d", target.database]
    )
    await _run(cmd, env, stdin=backup)


# ---------------------------------------------------------------- jobs e guarda


def backup_dir() -> Path:
    path = validate_backup_dir(settings.backup_dir)
    if settings.backup_dir_host:
        validate_backup_dir(settings.backup_dir_host)
    return path


PINNED_DADOS_FILE = (
    Path(__file__).resolve().parents[1] / "tests" / "dados_reais" / "pinned_backup.txt"
)


def pinned_dados_backup() -> Path | None:
    """Backup pré-migração fixado para a revisão sob teste (só o nome do arquivo fica no repo)."""
    if not PINNED_DADOS_FILE.is_file():
        return None
    name = PINNED_DADOS_FILE.read_text().strip()
    return backup_dir() / PRE_MIGRATION_SUBDIR / name if name else None


def list_backups(directory: Path, db: str) -> list[Path]:
    if not directory.is_dir():
        return []
    found = [p for p in directory.iterdir() if p.is_file() and _backup_db(p.name) == db]
    return sorted(
        found, key=lambda p: parse_backup_moment(p.name) or datetime.min.replace(tzinfo=UTC)
    )


def latest_backup(db: str, *, include_pre_migration: bool = True) -> Path | None:
    root = backup_dir()
    candidates = list_backups(root, db)
    if include_pre_migration:
        candidates += list_backups(root / PRE_MIGRATION_SUBDIR, db)
    if not candidates:
        return None
    return max(
        candidates, key=lambda p: parse_backup_moment(p.name) or datetime.min.replace(tzinfo=UTC)
    )


async def make_pre_migration_backup(dsn: str, tag: str, now: datetime | None = None) -> Path:
    target = DbTarget.from_dsn(dsn)
    moment = now or datetime.now(UTC)
    dest = backup_dir() / PRE_MIGRATION_SUBDIR / backup_name(target.database, moment, tag)
    await dump(dsn, dest)
    logger.info("backup_pre_migracao_ok", database=target.database, file=dest.name)
    return dest


_ALEMBIC_WRITES = frozenset({"upgrade", "downgrade", "stamp"})


def alembic_command_writes(cmd_opts: Any) -> bool:
    """O comando Alembic em curso escreve no banco? Programático (sem cmd_opts) conta como escrita;
    `current`, `history`, `heads` etc. não pedem backup."""
    cmd = getattr(cmd_opts, "cmd", None)
    if cmd is None:
        return True
    return getattr(cmd[0], "__name__", "") in _ALEMBIC_WRITES


async def ensure_recent_backup(
    dsn: str, *, reason: str, now: datetime | None = None
) -> Path | None:
    """Guarda antes de escrever dado: banco descartável passa; senão exige backup com menos de 1 h
    (diário ou pré-migração) ou faz um agora. Falha no backup levanta — quem chamou não escreve."""
    target = DbTarget.from_dsn(dsn)
    if is_disposable_db(target.database):
        return None
    moment = now or datetime.now(UTC)
    last = latest_backup(target.database)
    if last is not None:
        taken = parse_backup_moment(last.name)
        if taken is not None and moment - taken < RECENT_BACKUP_MAX_AGE:
            return last
    return await make_pre_migration_backup(dsn, reason, moment)


async def run_db_backup(dsn: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Job diário: dump na pasta diária + retenção por idade (pré-migração intocados)."""
    dsn = dsn or settings.database_url
    target = DbTarget.from_dsn(dsn)
    moment = now or datetime.now(UTC)
    root = backup_dir()
    dest = await dump(dsn, root / backup_name(target.database, moment))
    names = [p.name for p in list_backups(root, target.database)]
    deleted = retention_to_delete(names, moment.date())
    for name in deleted:
        (root / name).unlink(missing_ok=True)
    logger.info("db_backup_ok", database=target.database, file=dest.name, deleted=len(deleted))
    return {"file": dest.name, "size_bytes": dest.stat().st_size, "deleted": len(deleted)}


_CHECK_SQL = (
    ("transactions", "SELECT count(*)::text, COALESCE(sum(amount), 0)::text FROM transactions"),
    (
        "asset_operations",
        "SELECT count(*)::text, COALESCE(sum(quantidade * valor_unitario), 0)::text "
        "FROM asset_operations",
    ),
    ("accounts", "SELECT count(*)::text, '0' FROM accounts"),
    ("categories", "SELECT count(*)::text, '0' FROM categories"),
)


async def _fingerprint(dsn: str) -> dict[str, tuple[str, str]]:
    conn = await asyncpg.connect(dsn)
    try:
        out: dict[str, tuple[str, str]] = {}
        for table, sql in _CHECK_SQL:
            row = await conn.fetchrow(sql)
            out[table] = (row[0], row[1])
        return out
    finally:
        await conn.close()


async def run_restore_check(dsn: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Job mensal: backup novo → restaura num banco descartável → contagens e totais iguais ao
    banco de origem. Divergência levanta (o job fica com erro e vira aviso de worker)."""
    dsn = dsn or settings.database_url
    fresh = await run_db_backup(dsn, now)
    source = DbTarget.from_dsn(dsn)
    scratch = source.with_database("goodies_restore_check")
    await restore(backup_dir() / fresh["file"], scratch.dsn())
    try:
        expected = await _fingerprint(dsn)
        got = await _fingerprint(scratch.dsn())
    finally:
        await recreate_database(scratch)
    mismatched = sorted(t for t in expected if expected[t] != got.get(t))
    if mismatched:
        raise BackupError(f"restauração divergente em: {', '.join(mismatched)}")
    logger.info("restore_check_ok", database=source.database, tables=len(expected))
    return {"file": fresh["file"], "tables": len(expected), "match": True}
