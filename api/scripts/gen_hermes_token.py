"""Gera o Hermes service token — STORY-00-05 / ADR-006/007.

JWT scope=hermes, expiração HERMES_TOKEN_TTL_DAYS (90d), assinado com
HERMES_SERVICE_TOKEN_SECRET (gere o secret com `python -c "import secrets;
print(secrets.token_hex(32))"` e configure no Fly.io — NÃO commitar).

Uso (a partir de api/):
    .venv/bin/python -m scripts.gen_hermes_token
"""

from datetime import UTC, datetime, timedelta

from jose import jwt

from config import settings


def generate_hermes_token() -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.hermes_token_ttl_days)
    payload = {"sub": "hermes", "scope": "hermes", "type": "access", "exp": expire}
    return str(jwt.encode(payload, settings.hermes_service_token_secret, algorithm="HS256"))


if __name__ == "__main__":
    print(generate_hermes_token())
