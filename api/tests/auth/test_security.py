"""STORY-00-05 — camada de cripto de auth (senha + JWT). RED-first.

Unitário (sem DB): hash/verify de senha e encode/decode de JWT, incl. expirado/inválido.
"""

from datetime import UTC, datetime, timedelta

import pytest
from jose import ExpiredSignatureError, JWTError, jwt

from auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from config import settings


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_roundtrip_carries_subject_and_scope():
    token = create_access_token("user-123", scope="user")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["scope"] == "user"


def test_decode_invalid_token_raises():
    with pytest.raises(JWTError):
        decode_access_token("not.a.real.token")


def test_decode_expired_token_raises():
    expired = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(expired)
