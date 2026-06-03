"""Configuração da aplicação via pydantic-settings — STORY-00-02.

Lê variáveis de ambiente (e `.env` em dev). Valores ausentes usam os defaults
abaixo. Em produção (Fly.io) as variáveis vêm de secrets, não de arquivo `.env`.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_DATABASE_URL = "postgresql://goodies:goodies@localhost:5432/goodies"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = _DEV_DATABASE_URL

    @field_validator("database_url", mode="before")
    @classmethod
    def _fallback_database_url(cls, v: object) -> object:
        # .env de dev pode trazer DATABASE_URL= (vazio) → usa o Postgres local do compose.
        if v is None or (isinstance(v, str) and not v.strip()):
            return _DEV_DATABASE_URL
        return v


settings = Settings()
