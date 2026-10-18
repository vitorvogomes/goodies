"""Story 1.2 — regras puras do backup: nome, retenção por idade e diretório recusado."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from workers.backup import (
    BackupDirError,
    backup_name,
    is_disposable_db,
    parse_backup_moment,
    retention_to_delete,
    validate_backup_dir,
)


def test_backup_name_has_db_and_timestamp() -> None:
    moment = datetime(2026, 10, 18, 5, 6, 7, tzinfo=UTC)
    assert backup_name("goodies", moment) == "goodies_20261018_050607.dump"
    assert backup_name("goodies", moment, tag="pre-0016") == "goodies_20261018_050607_pre-0016.dump"


def test_parse_backup_moment_roundtrip_and_foreign_files() -> None:
    moment = datetime(2026, 10, 18, 5, 6, 7, tzinfo=UTC)
    assert parse_backup_moment(backup_name("goodies", moment, tag="x")) == moment
    assert parse_backup_moment("notas.txt") is None
    assert parse_backup_moment("goodies_2026_bad.dump") is None


def _names(days: list[date]) -> list[str]:
    return [backup_name("goodies", datetime(d.year, d.month, d.day, 3, tzinfo=UTC)) for d in days]


def test_retention_keeps_30_days_by_age_even_with_many_restarts() -> None:
    today = date(2026, 10, 18)
    # 5 backups por dia nos últimos 3 dias (reinícios) não encurtam a janela de 30 dias
    recent = [
        backup_name("goodies", datetime(2026, 10, d, h, tzinfo=UTC))
        for d in (16, 17, 18)
        for h in range(5)
    ]
    older_in_window = _names([date(2026, 9, 19), date(2026, 9, 25)])
    assert retention_to_delete(recent + older_in_window, today) == []


def test_retention_keeps_newest_of_each_of_last_12_months() -> None:
    today = date(2026, 10, 18)
    names = _names(
        [
            date(2026, 8, 3),
            date(2026, 8, 20),  # mais novo de agosto → fica
            date(2025, 11, 2),  # 11 meses atrás → fica
            date(2025, 10, 1),  # 12º mês atrás → fica
            date(2025, 9, 30),  # 13 meses → apaga
        ]
    )
    deleted = retention_to_delete(names, today)
    assert sorted(deleted) == sorted(_names([date(2026, 8, 3), date(2025, 9, 30)]))


def test_retention_ignores_files_it_does_not_recognize() -> None:
    assert retention_to_delete(["LEIA-ME.txt"], date(2026, 10, 18)) == []


@pytest.mark.parametrize(
    "path",
    [
        "/mnt/c/Users/vitor/OneDrive/backups",
        "/home/v/Dropbox/goodies",
        "/mnt/g/My Drive/goodies",
        "/home/v/Google Drive/x",
        "/home/v/iCloudDrive/x",
    ],
)
def test_cloud_synced_backup_dir_is_refused(path: str, tmp_path: Path) -> None:
    with pytest.raises(BackupDirError, match="nuvem"):
        validate_backup_dir(path, repo_root=tmp_path / "repo")


def test_backup_dir_inside_repo_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(BackupDirError, match="repositório"):
        validate_backup_dir(str(repo / "backups"), repo_root=repo)


def test_empty_backup_dir_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BackupDirError, match="BACKUP_DIR"):
        validate_backup_dir("", repo_root=tmp_path)


def test_valid_backup_dir_is_returned(tmp_path: Path) -> None:
    target = tmp_path / "goodies-backups"
    assert validate_backup_dir(str(target), repo_root=tmp_path / "repo") == target


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("goodies", False),
        ("goodies_test", True),
        ("goodies_dados", True),
        ("goodies_dev", True),
        ("goodies_tmp_restore", True),
    ],
)
def test_disposable_db_names(name: str, expected: bool) -> None:
    assert is_disposable_db(name) is expected


def test_without_repo_only_cloud_check_applies(tmp_path: Path) -> None:
    # no container o código não é um repositório git: /backups é aceito
    assert validate_backup_dir("/backups", repo_root=Path("/")) == Path("/backups")


def test_relative_backup_dir_is_refused(tmp_path: Path) -> None:
    # review e1: relativo, o compose resolve contra o repo (dump do banco no working tree)
    with pytest.raises(BackupDirError, match="absoluto"):
        validate_backup_dir("./backups", repo_root=Path("/"))


def test_dsn_roundtrip_quotes_special_characters() -> None:
    from workers.backup import DbTarget

    dsn = "postgresql://goodies:p%40ss%2Fw%3Ard%23@localhost:5432/goodies"
    target = DbTarget.from_dsn(dsn)
    assert target.password == "p@ss/w:rd#"
    assert DbTarget.from_dsn(target.with_database("goodies_dev").dsn()).password == "p@ss/w:rd#"
