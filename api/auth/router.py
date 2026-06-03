"""Rotas de auth — STORY-00-05 / ADR-006.

POST /login (email+senha → tokens), POST /refresh (refresh → novo access),
GET /me (protegida). O refresh token é guardado como hash em users.refresh_token_hash.
"""

import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from jose import JWTError
from pydantic import BaseModel

from auth.dependencies import get_current_user
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_token,
    verify_password,
)
from config import settings
from db.connection import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    expires_in: int


def _access_ttl_seconds() -> int:
    return settings.jwt_access_ttl_minutes * 60


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[asyncpg.Connection, Depends(get_db)],
) -> TokenResponse:
    row = await db.fetchrow(
        "SELECT id, password_hash FROM users WHERE email = $1", body.email
    )
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "email ou senha inválidos")

    user_id = str(row["id"])
    access = create_access_token(user_id, scope="user")
    refresh = create_refresh_token(user_id)
    await db.execute(
        "UPDATE users SET refresh_token_hash = $1 WHERE id = $2",
        hash_token(refresh),
        row["id"],
    )
    # Refresh em httpOnly cookie (ADR-006) — o proxy.ts do front usa p/ gating.
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=settings.jwt_refresh_ttl_days * 86400,
        path="/",
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=_access_ttl_seconds(),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[asyncpg.Connection, Depends(get_db)],
) -> AccessTokenResponse:
    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id = uuid.UUID(str(payload.get("sub")))
    except (JWTError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "refresh token inválido ou expirado"
        ) from None

    row = await db.fetchrow("SELECT id, refresh_token_hash FROM users WHERE id = $1", user_id)
    if row is None or row["refresh_token_hash"] != hash_token(body.refresh_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revogado")

    access = create_access_token(str(row["id"]), scope="user")
    return AccessTokenResponse(access_token=access, expires_in=_access_ttl_seconds())


@router.get("/me")
async def me(current_user: Annotated[dict[str, str], Depends(get_current_user)]) -> dict[str, str]:
    return current_user
