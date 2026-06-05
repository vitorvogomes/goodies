"""Rotas de auth — STORY-00-05 / ADR-006.

POST /login (email+senha → tokens), POST /refresh (refresh → novo access),
GET /me (protegida). O refresh token é guardado como hash em users.refresh_token_hash.
"""

import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Seta o refresh token como cookie httpOnly (ADR-006). Usado no login e refresh."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=settings.jwt_refresh_ttl_days * 86400,
        path="/",
    )


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
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=_access_ttl_seconds(),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[asyncpg.Connection, Depends(get_db)],
    body: RefreshRequest | None = None,
) -> AccessTokenResponse:
    # O browser não lê o cookie httpOnly → manda só o cookie. Clientes/testes podem
    # mandar no body (precedência). Pelo menos uma das fontes precisa existir.
    token = (body.refresh_token if body else None) or request.cookies.get(
        "refresh_token"
    )
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token ausente")

    try:
        payload = decode_refresh_token(token)
        user_id = uuid.UUID(str(payload.get("sub")))
    except (JWTError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "refresh token inválido ou expirado"
        ) from None

    row = await db.fetchrow(
        "SELECT id, refresh_token_hash FROM users WHERE id = $1", user_id
    )
    if row is None or row["refresh_token_hash"] != hash_token(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revogado")

    user_id_str = str(row["id"])
    access = create_access_token(user_id_str, scope="user")
    # Rotação: novo refresh, atualiza o hash no DB e re-seta o cookie (janela
    # deslizante de 30 dias — usuário ativo nunca cai).
    new_refresh = create_refresh_token(user_id_str)
    await db.execute(
        "UPDATE users SET refresh_token_hash = $1 WHERE id = $2",
        hash_token(new_refresh),
        row["id"],
    )
    _set_refresh_cookie(response, new_refresh)
    return AccessTokenResponse(access_token=access, expires_in=_access_ttl_seconds())


@router.get("/me")
async def me(current_user: Annotated[dict[str, str], Depends(get_current_user)]) -> dict[str, str]:
    return current_user
