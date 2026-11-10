"""ADR-018 — subida do container no Railway: host/porta pela env e admin do bootstrap."""

from __future__ import annotations

import pytest

from config import Settings
from scripts.ops import startup


@pytest.fixture(autouse=True)
def _no_server_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings(_env_file=None) ainda lê o ambiente do processo (container com PORT/REDIS_URL)."""
    for name in ("PORT", "API_HOST", "DATABASE_URL", "REDIS_URL", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)


def test_uvicorn_argv_defaults_to_compose_host_and_port() -> None:
    s = Settings(_env_file=None)
    assert startup.uvicorn_argv(s) == [
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]


def test_uvicorn_argv_reads_api_host_and_port() -> None:
    s = Settings(_env_file=None, api_host="::", port=9123)
    assert startup.uvicorn_argv(s)[-4:] == ["--host", "::", "--port", "9123"]


def test_port_comes_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_HOST", "::")
    s = Settings(_env_file=None)
    assert (s.api_host, s.port) == ("::", 8080)


def test_production_without_service_urls_refuses_before_touching_the_db(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-018: sem DATABASE_URL/REDIS_URL em produção, a subida para com o nome das variáveis
    (nunca o valor) antes do backup e do gate de migração."""
    s = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://u:segredo@postgres.railway.internal:5432/railway",
    )
    monkeypatch.setattr(startup, "settings", s)

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("não devia chegar ao banco")

    monkeypatch.setattr(startup, "backup_dir", _boom)
    monkeypatch.setattr(startup, "startup_gate", _boom)
    with pytest.raises(SystemExit) as exc:
        startup.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "REDIS_URL" in err and "DATABASE_URL" not in err
    assert "segredo" not in err
