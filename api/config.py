"""Configuração da aplicação via pydantic-settings — STORY-00-02.

Lê variáveis de ambiente (e `.env` em dev). Valores ausentes usam os defaults
abaixo. Em produção (Fly.io) as variáveis vêm de secrets, não de arquivo `.env`.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
