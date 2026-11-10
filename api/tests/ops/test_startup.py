"""ADR-018 — subida do container no Railway: host/porta pela env e admin do bootstrap."""

from __future__ import annotations

from config import Settings
from scripts.ops import startup


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
