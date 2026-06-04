"""CRUD de categorias (STORY-01-02).

Lista configurável que alimenta o dropdown do front e a classificação do import.
transactions.category permanece TEXT livre (sem FK). name é único → POST duplicado
retorna 409.
"""

import uuid
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api/v1/categories", tags=["ledger:categories"])

CategoryKind = Literal["income", "expense", "investment", "transfer"]

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    kind: CategoryKind
    match_patterns: list[str] = []  # substrings p/ auto-classificar o import (destinos)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    kind: CategoryKind | None = None
    is_active: bool | None = None
    match_patterns: list[str] | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    kind: str
    is_active: bool
    match_patterns: list[str]


def _to_response(row: asyncpg.Record) -> CategoryResponse:
    return CategoryResponse(
        id=str(row["id"]),
        name=row["name"],
        kind=row["kind"],
        is_active=row["is_active"],
        match_patterns=list(row["match_patterns"]),
    )


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    user: AuthUser,
    db: Db,
    kind: Annotated[CategoryKind | None, Query()] = None,
    active: Annotated[bool | None, Query()] = None,
) -> list[CategoryResponse]:
    rows = await db.fetch(
        """
        SELECT id, name, kind, is_active, match_patterns FROM categories
        WHERE ($1::text IS NULL OR kind = $1)
          AND ($2::boolean IS NULL OR is_active = $2)
        ORDER BY kind, name
        """,
        kind,
        active,
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(body: CategoryCreate, user: AuthUser, db: Db) -> CategoryResponse:
    try:
        row = await db.fetchrow(
            "INSERT INTO categories (name, kind, match_patterns) VALUES ($1, $2, $3) "
            "RETURNING id, name, kind, is_active, match_patterns",
            body.name,
            body.kind,
            body.match_patterns,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "categoria já existe") from None
    return _to_response(row)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID, body: CategoryUpdate, user: AuthUser, db: Db
) -> CategoryResponse:
    try:
        row = await db.fetchrow(
            """
            UPDATE categories SET
              name = COALESCE($2, name),
              kind = COALESCE($3, kind),
              is_active = COALESCE($4, is_active),
              match_patterns = COALESCE($5, match_patterns)
            WHERE id = $1
            RETURNING id, name, kind, is_active, match_patterns
            """,
            category_id,
            body.name,
            body.kind,
            body.is_active,
            body.match_patterns,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "categoria já existe") from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
    return _to_response(row)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute("DELETE FROM categories WHERE id = $1", category_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
