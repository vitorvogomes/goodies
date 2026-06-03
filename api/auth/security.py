"""Cripto de auth — STORY-00-05 / ADR-006.

Senha: passlib[bcrypt] (bcrypt<5; ver pyproject). JWT: python-jose (HS256).
Access token (scope user/hermes) e refresh token usam segredos distintos.
O refresh token é guardado no banco como SHA-256 (hash, não o token).
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return str(_pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(_pwd_context.verify(password, password_hash))


def create_access_token(subject: str, scope: str = "user") -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload = {"sub": subject, "scope": scope, "type": "access", "exp": expire}
    return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM))


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {"sub": subject, "type": "refresh", "exp": expire}
    return str(jwt.encode(payload, settings.jwt_refresh_secret_key, algorithm=_ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(
        token, settings.jwt_refresh_secret_key, algorithms=[_ALGORITHM]
    )
    return payload


def hash_token(token: str) -> str:
    """SHA-256 do refresh token p/ guardar em users.refresh_token_hash."""
    return hashlib.sha256(token.encode()).hexdigest()
