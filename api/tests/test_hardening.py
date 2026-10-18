"""Story 1.6 — segredos dev-insecure recusados, Hermes desligado por padrão, Redis pela config."""
from __future__ import annotations

import importlib

import pytest

import config
from config import Settings, insecure_secrets


def test_default_secrets_are_refused_outside_test() -> None:
    s = Settings(_env_file=None, environment="development")
    assert sorted(insecure_secrets(s)) == [
        "hermes_service_token_secret",
        "jwt_refresh_secret_key",
        "jwt_secret_key",
    ]
    with pytest.raises(RuntimeError, match="dev-insecure"):
        config.assert_secure(s)


def test_test_environment_may_use_dev_secrets() -> None:
    config.assert_secure(Settings(_env_file=None, environment="test"))


def test_real_secrets_pass() -> None:
    s = Settings(
        _env_file=None,
        environment="development",
        jwt_secret_key="a" * 64,
        jwt_refresh_secret_key="b" * 64,
        hermes_service_token_secret="c" * 64,
    )
    config.assert_secure(s)


def test_hermes_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_ENABLED", raising=False)  # a suíte liga o Hermes no conftest
    assert Settings(_env_file=None).hermes_enabled is False


def test_hermes_router_not_mounted_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import main

    monkeypatch.setattr(config.settings, "hermes_enabled", False)
    reloaded = importlib.reload(main)
    try:
        paths = {getattr(r, "path", "") for r in reloaded.app.routes}
        assert not any(p.startswith("/api/v1/hermes") for p in paths)
    finally:
        monkeypatch.setattr(config.settings, "hermes_enabled", True)
        importlib.reload(main)


def test_redis_url_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from engines.common.cache import _resolve_url

    monkeypatch.setattr(config.settings, "redis_url", "redis://:segredo@localhost:6379/3")
    assert _resolve_url(None) == "redis://:segredo@localhost:6379/3"


@pytest.mark.parametrize(
    "secret",
    ["change_me_openssl_rand_hex_32", "change_me_another_random_hex_32", "curto-demais"],
)
def test_placeholder_or_short_secrets_are_refused(secret: str) -> None:
    # review e1: o .env.example publica placeholders; copiado sem editar, a api não pode subir
    s = Settings(
        _env_file=None,
        environment="development",
        jwt_secret_key=secret,
        jwt_refresh_secret_key="b" * 64,
        hermes_service_token_secret="c" * 64,
    )
    assert insecure_secrets(s) == ["jwt_secret_key"]
    with pytest.raises(RuntimeError):
        config.assert_secure(s)
