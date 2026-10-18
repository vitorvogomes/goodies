"""Dependências FastAPI compartilhadas (AD-2 — Story 2.1): `Db` e `AuthUser`."""
from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import Depends

from auth.dependencies import get_current_user
from db.connection import get_db

Db = Annotated[asyncpg.Connection, Depends(get_db)]
AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
