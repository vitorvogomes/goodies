"""Portfolio router — asset operations endpoints.

Note: B008 (Depends in defaults) is standard FastAPI pattern and safe here.
"""
from __future__ import annotations

# ruff: noqa: B008
from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from auth.dependencies import get_current_user
from db.connection import get_db

from . import operations, service

router = APIRouter(prefix="/api/v1/asset-operations", tags=["portfolio"])

# Valid operation types (mirrors CHECK constraint in DB)
VALID_TIPOS = {"compra", "venda", "dividendo", "juros", "aporte", "resgate"}


class CreateAssetOperationRequest(BaseModel):
    """Request body for creating an asset operation."""

    broker: str
    asset_symbol: str
    asset_category: str
    tipo: str
    quantidade: float = Field(..., gt=0)  # > 0
    valor_unitario: float = Field(..., ge=0)  # >= 0
    data_operacao: date
    notes: str | None = None
    external_id: str | None = None

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        """Validate tipo is in allowed set."""
        if v not in VALID_TIPOS:
            raise ValueError(f"tipo must be one of {VALID_TIPOS}")
        return v


class AssetOperationResponse(BaseModel):
    """Response model for asset operation."""

    id: str
    user_id: str
    broker: str
    asset_symbol: str
    asset_category: str
    tipo: str
    quantidade: float
    valor_unitario: float
    data_operacao: date
    notes: str | None
    external_id: str | None
    created_at: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_asset_operation(
    body: CreateAssetOperationRequest,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Create a new asset operation."""
    user_id = user["id"]

    try:
        result = await operations.create_operation(
            db,
            user_id=user_id,
            broker=body.broker,
            asset_symbol=body.asset_symbol,
            asset_category=body.asset_category,
            tipo=body.tipo,
            quantidade=body.quantidade,
            valor_unitario=body.valor_unitario,
            data_operacao=body.data_operacao,
            notes=body.notes,
            external_id=body.external_id,
        )
        await service.invalidate_xirr_cache(user_id)
        return result
    except asyncpg.CheckViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid operation type or quantity/value constraint violation",
        ) from exc
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_id already exists",
        ) from exc


@router.get("")
async def list_asset_operations(
    asset_symbol: str | None = Query(None),
    tipo: str | None = Query(None),
    data_from: date | None = Query(None),
    data_to: date | None = Query(None),
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """List asset operations with optional filters."""
    user_id = user["id"]
    return await operations.list_operations(
        db,
        user_id=user_id,
        asset_symbol=asset_symbol,
        tipo=tipo,
        data_from=data_from,
        data_to=data_to,
    )


@router.get("/dca")
async def list_dca_all(
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """List DCA (preço médio ponderado) for all assets."""
    user_id = user["id"]
    return await operations.calculate_dca_all(db, user_id)


@router.get("/dca/{asset_symbol}")
async def get_dca_by_asset(
    asset_symbol: str,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Get DCA for a specific asset (404 if no compra/aporte ops)."""
    user_id = user["id"]
    result = await operations.calculate_dca_by_asset(db, user_id, asset_symbol)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.get("/{operation_id}")
async def get_asset_operation(
    operation_id: str,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Get a single asset operation by ID."""
    user_id = user["id"]
    result = await operations.get_operation(db, user_id, operation_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/{operation_id}")
async def update_asset_operation(
    operation_id: str,
    body: CreateAssetOperationRequest,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Update an asset operation."""
    user_id = user["id"]

    try:
        result = await operations.update_operation(
            db,
            user_id=user_id,
            operation_id=operation_id,
            broker=body.broker,
            asset_symbol=body.asset_symbol,
            asset_category=body.asset_category,
            tipo=body.tipo,
            quantidade=body.quantidade,
            valor_unitario=body.valor_unitario,
            data_operacao=body.data_operacao,
            notes=body.notes,
            external_id=body.external_id,
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await service.invalidate_xirr_cache(user_id)
        return result
    except asyncpg.CheckViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid operation type or quantity/value constraint violation",
        ) from exc
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_id already exists",
        ) from exc


@router.delete("/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_operation(
    operation_id: str,
    user: dict[str, str] = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
) -> None:
    """Delete an asset operation."""
    user_id = user["id"]
    deleted = await operations.delete_operation(db, user_id, operation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await service.invalidate_xirr_cache(user_id)
