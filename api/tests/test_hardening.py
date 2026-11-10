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


def test_api_docs_off_in_production() -> None:
    """ADR-018: a api não publica /docs, /redoc nem o schema em produção."""
    assert config.api_docs_urls("production") == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert config.api_docs_urls("development") == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


def test_postgres_scheme_is_normalized() -> None:
    """ADR-018: `postgres://` (alguns provedores) vira `postgresql://` (exigido pelo env.py)."""
    s = Settings(_env_file=None, database_url="postgres://u:p@h:5432/db")
    assert s.database_url == "postgresql://u:p@h:5432/db"
    s = Settings(_env_file=None, database_url="postgresql://u:p@h:5432/db")
    assert s.database_url == "postgresql://u:p@h:5432/db"


@pytest.mark.parametrize("field", ["LBTC_ASSET_ID", "LUSDT_ASSET_ID"])
def test_blank_liquid_asset_id_keeps_the_constant(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """Um `LBTC_ASSET_ID=` vazio de um .env antigo não apaga o saldo da SideSwap em silêncio."""
    monkeypatch.setenv(field, "")
    default = Settings.model_fields[field.lower()].default
    assert getattr(Settings(_env_file=None), field.lower()) == default


def test_liquid_public_constants_live_in_code() -> None:
    """ADR-005: constantes públicas da Liquid e da Blockstream ficam no código, não no .env."""
    s = Settings(_env_file=None)
    assert s.lbtc_asset_id == "6f0279e9ed041c3d710a9f57d0c02928416460c4b722ae3457a11eec381c526d"
    assert s.lusdt_asset_id == "ce091c998b83c78bb71a632313ba3760f1763d9cfcffae02258ffa9865a37bd2"
    assert s.liquid_base_url == "https://blockstream.info/liquid/api"
    assert s.btc_base_url == "https://blockstream.info/api"


def test_cors_closed_by_default() -> None:
    """ADR-018: nenhuma origem externa liberada por padrão (o web repassa /api/v1)."""
    assert Settings(_env_file=None).cors_origins == []


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, ["DATABASE_URL", "REDIS_URL"]),
        ({"database_url": "", "redis_url": " "}, ["DATABASE_URL", "REDIS_URL"]),
        (
            {"database_url": "postgresql://u:p@postgres.railway.internal:5432/railway"},
            ["REDIS_URL"],
        ),
        ({"redis_url": "redis://default:p@127.0.0.1:6379"}, ["DATABASE_URL", "REDIS_URL"]),
        (
            {
                "database_url": "postgresql://u:p@postgres.railway.internal:5432/railway",
                "redis_url": "redis://default:p@redis.railway.internal:6379",
            },
            [],
        ),
    ],
)
def test_production_refuses_local_service_urls(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: list[str]
) -> None:
    """ADR-018: em produção, DATABASE_URL/REDIS_URL vazias não caem em silêncio no localhost do dev
    (aconteceu duas vezes no 1º deploy do Railway, 10/11/2026)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    s = Settings(_env_file=None, environment="production", **env)
    assert config.local_service_urls(s) == expected


def test_local_service_urls_are_fine_outside_production() -> None:
    assert config.local_service_urls(Settings(_env_file=None, environment="development")) == []
