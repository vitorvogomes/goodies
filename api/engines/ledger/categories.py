"""CRUD de categorias v1 (STORY-01-02), mantido por cima do modelo v2 até a tela sair.

Lista que alimenta o dropdown das telas v1. `name` é único → POST duplicado retorna 409.
"""

import uuid
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.ledger import service as ledger_service
from engines.ledger.models import SubcategoryUpdate

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


# v2 (Story 2.4/2.9): o import lê só `category_rules` e o kind vem do grupo. A tela v1 continua
# funcionando por cima disso: `match_patterns` é a lista das regras ativas da categoria (gravar a
# lista cria/reativa/desativa regras de origem manual) e o kind só muda em Ajustes › Categorias.
_DIRECTION_BY_KIND = {
    "income": "entrada",
    "expense": "saida",
    "investment": "saida",
    "transfer": "ambos",
}
_SELECT = """
    SELECT c.id, c.name, g.kind, c.is_active,
           coalesce((SELECT array_agg(DISTINCT r.pattern ORDER BY r.pattern) FROM category_rules r
                     WHERE r.category_id = c.id AND r.is_active), '{}') AS match_patterns
    FROM categories c JOIN category_groups g ON g.id = c.group_id
"""


def _normalize(patterns: list[str]) -> list[str]:
    seen: list[str] = []
    for p in patterns:
        q = p.strip().lower()
        if q and q not in seen:
            seen.append(q)
    return seen


async def _sync_rules(
    db: asyncpg.Connection, category_id: uuid.UUID, kind: str, patterns: list[str]
) -> None:
    await db.execute(
        "UPDATE category_rules SET is_active = false "
        "WHERE category_id = $1 AND is_active AND pattern <> ALL($2::text[])",
        category_id,
        patterns,
    )
    for pattern in patterns:
        await db.execute(
            "INSERT INTO category_rules (pattern, direction, category_id, origin) "
            "VALUES ($1, $2, $3, 'manual') ON CONFLICT (pattern, direction, category_id) "
            "DO UPDATE SET is_active = true",
            pattern,
            _DIRECTION_BY_KIND[kind],
            category_id,
        )


async def _fetch(db: asyncpg.Connection, category_id: uuid.UUID) -> asyncpg.Record | None:
    row: asyncpg.Record | None = await db.fetchrow(_SELECT + " WHERE c.id = $1", category_id)
    return row


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
        _SELECT
        + """
        WHERE NOT g.is_system AND ($1::text IS NULL OR g.kind = $1)
          AND ($2::boolean IS NULL OR c.is_active = $2)
        ORDER BY g.kind, c.name
        """,
        kind,
        active,
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(body: CategoryCreate, user: AuthUser, db: Db) -> CategoryResponse:
    patterns = _normalize(body.match_patterns)
    async with db.transaction():
        try:
            # Sem grupo: trg_categories_defaults põe no grupo padrão do kind (Story 2.3).
            cid = await db.fetchval(
                "INSERT INTO categories (name, kind) VALUES ($1, $2) RETURNING id",
                body.name,
                body.kind,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status.HTTP_409_CONFLICT, "categoria já existe") from None
        await _sync_rules(db, cid, body.kind, patterns)
        row = await _fetch(db, cid)
    assert row is not None
    return _to_response(row).model_copy(update={"match_patterns": patterns})


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID, body: CategoryUpdate, user: AuthUser, db: Db
) -> CategoryResponse:
    async with db.transaction():
        current = await _fetch(db, category_id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
        if body.kind is not None and body.kind != current["kind"]:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "o tipo vem do grupo: mude em Ajustes › Categorias"
            )
        try:
            await ledger_service.update_category(
                db,
                str(category_id),
                SubcategoryUpdate(name=body.name, is_active=body.is_active),
            )
        except ledger_service.CategoryRuleError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
        patterns = None
        if body.match_patterns is not None:
            patterns = _normalize(body.match_patterns)
            await _sync_rules(db, category_id, current["kind"], patterns)
        row = await _fetch(db, category_id)
    assert row is not None
    response = _to_response(row)
    return (
        response if patterns is None else response.model_copy(update={"match_patterns": patterns})
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    try:
        found = await ledger_service.delete_category(db, str(category_id))
    except ledger_service.CategoryRuleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "categoria não encontrada")
