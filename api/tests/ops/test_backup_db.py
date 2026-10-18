"""Story 1.2 — backup e restauração contra Postgres de teste (nunca o banco real)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from config import settings
from tests.conftest import TEST_DSN
from workers import backup
from workers.backup import DbTarget

_SCRATCH = DbTarget.from_dsn(TEST_DSN).with_database("goodies_tmp_restore").dsn()


@pytest.fixture
def backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "goodies-backups"
    monkeypatch.setattr(settings, "backup_dir", str(root))
    monkeypatch.setattr(settings, "backup_dir_host", "")
    return root


async def _seed(pool: Any) -> None:
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
            f"Conta bkp {uuid.uuid4().hex[:6]}",
        )
        await conn.execute(
            "INSERT INTO transactions (account_id, date, description, amount, category) "
            "VALUES ($1, '2026-06-01', 'bkp', -10.50, 'Outros')",
            acc,
        )


async def _counts(dsn: str) -> tuple[int, int]:
    conn = await asyncpg.connect(dsn)
    try:
        tx = await conn.fetchval("SELECT count(*) FROM transactions")
        ops = await conn.fetchval("SELECT count(*) FROM asset_operations")
        return int(tx), int(ops)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_dump_and_restore_keep_counts(pool: Any, backup_root: Path) -> None:
    await _seed(pool)
    dest = await backup.dump(TEST_DSN, backup_root / "goodies_test_20261018_000000.dump")
    assert dest.stat().st_size > 0
    await backup.restore(dest, _SCRATCH)
    try:
        assert await _counts(_SCRATCH) == await _counts(TEST_DSN)
    finally:
        await backup.recreate_database(DbTarget.from_dsn(_SCRATCH))


@pytest.mark.asyncio
async def test_restore_refuses_non_disposable_target(backup_root: Path) -> None:
    real = DbTarget.from_dsn(TEST_DSN).with_database("goodies").dsn()
    with pytest.raises(backup.BackupError, match="descartáveis"):
        await backup.restore(backup_root / "x.dump", real)


def _old_and_pinned(root: Path) -> tuple[Path, Path]:
    pre = root / backup.PRE_MIGRATION_SUBDIR
    pre.mkdir(parents=True)
    old = root / "goodies_test_20250101_000000.dump"
    old.write_bytes(b"velho")
    pinned = pre / "goodies_test_20240101_000000_pre-0001.dump"
    pinned.write_bytes(b"pre")
    return old, pinned


@pytest.mark.asyncio
async def test_run_db_backup_writes_daily_file_and_applies_retention(
    pool: Any, backup_root: Path
) -> None:
    old, pinned = _old_and_pinned(backup_root)
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)

    stats = await backup.run_db_backup(TEST_DSN, now)

    assert stats["file"] == "goodies_test_20261018_120000.dump"
    assert stats["size_bytes"] > 0
    assert stats["deleted"] == 1
    daily = [p.name for p in backup.list_backups(backup_root, "goodies_test")]
    assert daily == [stats["file"]]
    pre = backup.list_backups(backup_root / backup.PRE_MIGRATION_SUBDIR, "goodies_test")
    assert pre == [pinned] and old.name not in daily  # pré-migração nunca sai pela retenção


@pytest.mark.asyncio
async def test_guard_skips_disposable_db(backup_root: Path) -> None:
    assert await backup.ensure_recent_backup(TEST_DSN, reason="alembic") is None
    assert backup.latest_backup("goodies_test") is None


@pytest.mark.asyncio
async def test_guard_reuses_recent_backup_or_makes_one(
    pool: Any, backup_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "_DISPOSABLE_DBS", frozenset())  # trata o banco de teste como real
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)

    made = await backup.ensure_recent_backup(TEST_DSN, reason="alembic", now=now)
    assert made is not None and made.parent.name == backup.PRE_MIGRATION_SUBDIR
    assert made.name == "goodies_test_20261018_120000_alembic.dump"

    reused = await backup.ensure_recent_backup(
        TEST_DSN, reason="alembic", now=now + timedelta(minutes=30)
    )
    assert reused == made

    later = await backup.ensure_recent_backup(
        TEST_DSN, reason="alembic", now=now + timedelta(hours=2)
    )
    assert later is not None and later != made


@pytest.mark.asyncio
async def test_guard_fails_when_backup_fails(
    backup_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "_DISPOSABLE_DBS", frozenset())
    missing = DbTarget.from_dsn(TEST_DSN).with_database("goodies_nao_existe").dsn()
    with pytest.raises(backup.BackupError):
        await backup.ensure_recent_backup(missing, reason="alembic")


@pytest.mark.asyncio
async def test_restore_check_matches_source(pool: Any, backup_root: Path) -> None:
    await _seed(pool)
    stats = await backup.run_restore_check(TEST_DSN, datetime(2026, 11, 1, 6, tzinfo=UTC))
    assert stats["match"] is True and stats["tables"] == 4


def test_cloud_backup_dir_host_is_refused(
    backup_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "backup_dir_host", "/mnt/c/Users/v/OneDrive/goodies")
    with pytest.raises(backup.BackupDirError):
        backup.backup_dir()


def test_alembic_guard_only_for_writing_commands() -> None:
    import types

    from workers.backup import alembic_command_writes

    def cmd(name: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(cmd=(types.SimpleNamespace(__name__=name), [], []))

    assert alembic_command_writes(None) is True  # command.upgrade programático
    assert alembic_command_writes(cmd("upgrade")) is True
    assert alembic_command_writes(cmd("downgrade")) is True
    assert alembic_command_writes(cmd("current")) is False
    assert alembic_command_writes(cmd("history")) is False
