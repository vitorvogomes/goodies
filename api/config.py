"""Configuração da aplicação via pydantic-settings — STORY-00-02.

Lê variáveis de ambiente (e `.env` em dev). Valores ausentes usam os defaults
abaixo. Em produção (Fly.io) as variáveis vêm de secrets, não de arquivo `.env`.
"""

from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# O `.env` (e o `.env.example`) ficam no raiz do repo, não em api/. Resolvemos o
# caminho absoluto p/ que `uv run` a partir de api/ leia o arquivo certo. Em
# produção (Fly.io/Docker) o arquivo não existe → cai p/ env vars + defaults.
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"

_DEV_DATABASE_URL = "postgresql://goodies:goodies@localhost:5432/goodies"
_DEV_SECRETS = {
    "jwt_secret_key": "dev-insecure-jwt-secret",
    "jwt_refresh_secret_key": "dev-insecure-refresh-secret",
    "hermes_service_token_secret": "dev-insecure-hermes-secret",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ROOT_ENV), extra="ignore")

    environment: str = "development"
    version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = _DEV_DATABASE_URL

    # Auth JWT (ADR-006). Secrets vazios no .env caem p/ defaults de dev.
    jwt_secret_key: str = _DEV_SECRETS["jwt_secret_key"]
    jwt_refresh_secret_key: str = _DEV_SECRETS["jwt_refresh_secret_key"]
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    hermes_service_token_secret: str = _DEV_SECRETS["hermes_service_token_secret"]
    hermes_token_ttl_days: int = 90

    # Import Nubank (STORY-01-13-14): nomes/CPF do próprio usuário (separados por
    # vírgula) p/ marcar transferências entre contas próprias como "transferência
    # interna" (fora do caixa). Vazio = sem detecção. Definir no .env (PII).
    ledger_self_identifiers: str = ""

    # Valoração pós-fixada (pré-m3): CDI anual de referência (fração) p/ caixinhas/CDB
    # do Nubank (engines.portfolio.rf_cdi). Provisório — o m5 importa a série do BCB.
    cdi_anual: float = 0.1065

    @field_validator("database_url", mode="before")
    @classmethod
    def _fallback_database_url(cls, v: object) -> object:
        # .env de dev pode trazer DATABASE_URL= (vazio) → usa o Postgres local do compose.
        if v is None or (isinstance(v, str) and not v.strip()):
            return _DEV_DATABASE_URL
        return v

    @field_validator(
        "jwt_secret_key",
        "jwt_refresh_secret_key",
        "hermes_service_token_secret",
        mode="before",
    )
    @classmethod
    def _fallback_secret(cls, v: object, info: ValidationInfo) -> object:
        # Secret vazio no .env → default de dev (inseguro; prod define via secrets).
        if info.field_name and (v is None or (isinstance(v, str) and not v.strip())):
            return _DEV_SECRETS[info.field_name]
        return v


settings = Settings()
