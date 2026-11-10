"""Story 1.2 — subida do container e `migrar` (pré-condições antes de tocar o banco real)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg
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


_ADMIN = dbops.AdminCredentials("admin@goodies.test", "s" * 24)


@pytest.mark.asyncio
async def test_startup_auto_migrate_backs_up_before_upgrade(
    empty_db: str, backup_root: Path
) -> None:
    calls: list[str] = []

    def fake_upgrade(dsn: str, target: str) -> None:
        pre = list((backup_root / backup.PRE_MIGRATION_SUBDIR).iterdir())
        calls.append(f"upgrade {target} com {len(pre)} backup")

    async def fake_seed(dsn: str, admin: dbops.AdminCredentials) -> None:
        calls.append(f"admin {admin.email}")

    decision = await dbops.startup_gate(
        empty_db, auto_migrate=True, upgrade=fake_upgrade, admin=_ADMIN, seed_admin=fake_seed
    )
    assert decision.ok
    # ADR-018: banco vazio → 0001 → admin → head (a 0016 exige um usuário).
    assert calls == [
        f"upgrade {dbops.BOOTSTRAP_REVISION} com 1 backup",
        "admin admin@goodies.test",
        "upgrade head com 1 backup",
    ]


@pytest.mark.asyncio
async def test_startup_refuses_empty_db_without_admin(empty_db: str, backup_root: Path) -> None:
    touched: list[str] = []
    decision = await dbops.startup_gate(
        empty_db, auto_migrate=True, upgrade=lambda dsn, rev: touched.append(rev), admin=None
    )
    assert not decision.ok
    assert "ADMIN_EMAIL" in decision.message and "ADMIN_PASSWORD" in decision.message
    assert touched == []


@pytest.mark.asyncio
async def test_startup_bootstraps_empty_db_to_head_with_owner_seeds(
    empty_db: str, backup_root: Path
) -> None:
    """Alembic de verdade: as sementes por usuário das migrações caem no admin."""
    decision = await dbops.startup_gate(empty_db, auto_migrate=True, admin=_ADMIN)
    assert decision.ok, decision.message
    assert await dbops.current_revision(empty_db) == dbops.head_revision()
    conn = await asyncpg.connect(empty_db)
    try:
        owner = await conn.fetchval("SELECT id FROM users WHERE email = $1", _ADMIN.email)
        assert owner is not None
        assert await conn.fetchval("SELECT count(*) FROM users") == 1
        for table in ("category_groups", "categories", "category_rules", "portfolio_targets"):
            mine = await conn.fetchval(f"SELECT count(*) FROM {table} WHERE user_id = $1", owner)
            assert mine > 0, table
    finally:
        await conn.close()


def test_admin_credentials_from_env() -> None:
    assert dbops.admin_from_env({}) is None
    assert dbops.admin_from_env({"ADMIN_EMAIL": "a@b.c", "ADMIN_PASSWORD": " "}) is None
    assert dbops.admin_from_env({"ADMIN_EMAIL": "a@b.c", "ADMIN_PASSWORD": "pw"}) == (
        dbops.AdminCredentials("a@b.c", "pw")
    )


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
