"""Dependências de auth — STORY-00-05 / ADR-006.

`get_current_user` protege rotas: valida o Bearer (access token) e resolve o
usuário no banco. 401 se ausente, inválido, expirado ou inexistente.
"""

import uuid
from typing import Annotated

import asyncpg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from auth.security import decode_access_token
from db.connection import get_db

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token ausente")
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido ou expirado") from None
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido") from None
    row = await db.fetchrow("SELECT id, email FROM users WHERE id = $1", user_id)
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuário não encontrado")
    return {"id": str(row["id"]), "email": row["email"]}
