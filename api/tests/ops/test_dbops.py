"""Story 1.2 — subida do container e `migrar` (pré-condições antes de tocar o banco real)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from config import settings
from tests.conftest import TEST_DSN
from workers import backup, dbops
from workers.backup import DbTarget

_EMPTY = DbTarget.from_dsn(TEST_DSN).with_database("goodies_tmp_empty").dsn()


@pytest.fixture
def backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "goodies-backups"
    monkeypatch.setattr(settings, "backup_dir", str(root))
    monkeypatch.setattr(settings, "backup_dir_host", "")
    return root


@pytest.fixture
async def empty_db() -> Any:
    target = DbTarget.from_dsn(_EMPTY)
    await backup.recreate_database(target)
    yield _EMPTY
    await backup.recreate_database(target)


@pytest.mark.asyncio
async def test_startup_ok_when_db_at_head(pool: Any) -> None:
    decision = await dbops.startup_gate(TEST_DSN, auto_migrate=False)
    assert decision.ok and dbops.head_revision() in decision.message


@pytest.mark.asyncio
async def test_startup_refuses_db_behind_head_without_auto_migrate(empty_db: str) -> None:
    decision = await dbops.startup_gate(empty_db, auto_migrate=False)
    assert not decision.ok
    assert "python -m scripts.ops.migrar" in decision.message


@pytest.mark.asyncio
async def test_startup_auto_migrate_backs_up_before_upgrade(
    empty_db: str, backup_root: Path
) -> None:
    calls: list[str] = []

    def fake_upgrade(dsn: str) -> None:
        pre = list((backup_root / backup.PRE_MIGRATION_SUBDIR).iterdir())
        calls.append(f"upgrade com {len(pre)} backup")

    decision = await dbops.startup_gate(empty_db, auto_migrate=True, upgrade=fake_upgrade)
    assert decision.ok and calls == ["upgrade com 1 backup"]


@pytest.mark.asyncio
async def test_migrar_runs_checks_then_backup_then_upgrade(tmp_path: Path) -> None:
    order: list[str] = []

    async def fake_backup(dsn: str, tag: str) -> Path:
        order.append(f"backup:{tag}")
        return tmp_path / "b.dump"

    taken = await dbops.migrar(
        TEST_DSN,
        check_git=lambda: order.append("git"),
        check_tests=lambda: order.append("dados_reais"),
        backup=fake_backup,
        upgrade=lambda dsn, rev: order.append(f"upgrade:{rev}"),
    )
    assert taken == tmp_path / "b.dump"
    assert order == ["git", "dados_reais", "backup:pre-head", "upgrade:head"]


@pytest.mark.asyncio
async def test_migrar_does_not_upgrade_when_backup_fails() -> None:
    upgraded: list[str] = []

    async def broken_backup(dsn: str, tag: str) -> Path:
        raise backup.BackupError("disco cheio")

    with pytest.raises(dbops.MigrationRefused, match="backup falhou"):
        await dbops.migrar(
            TEST_DSN,
            check_git=lambda: None,
            check_tests=lambda: None,
            backup=broken_backup,
            upgrade=lambda dsn, rev: upgraded.append(rev),
        )
    assert upgraded == []


@pytest.mark.asyncio
async def test_migrar_stops_at_first_refused_check() -> None:
    def dirty() -> None:
        raise dbops.MigrationRefused("a main tem mudanças não commitadas")

    touched: list[str] = []
    with pytest.raises(dbops.MigrationRefused, match="não commitadas"):
        await dbops.migrar(
            TEST_DSN,
            check_git=dirty,
            check_tests=lambda: touched.append("tests"),
            upgrade=lambda dsn, rev: touched.append("upgrade"),
        )
    assert touched == []


def test_git_main_clean_refuses_other_branch(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "feature", str(tmp_path)], check=True)
    with pytest.raises(dbops.MigrationRefused, match="main"):
        dbops.git_main_clean(tmp_path)
