"""Agregador de rotas do Ledger Engine (m1).

Cada sub-módulo expõe seu próprio APIRouter com prefixo /api/v1/...; este
agregador é incluído uma vez no main.py. Novos sub-routers (transactions,
cashflow, ...) entram aqui conforme as stories avançam.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db
from engines.ledger.accounts import router as accounts_router
from engines.ledger.alerts import router as alerts_router
from engines.ledger.cashflow import router as cashflow_router
from engines.ledger.categories import router as categories_router
from engines.ledger.fixed_costs import router as fixed_costs_router
from engines.ledger.import_routes import router as import_router
from engines.ledger.transactions import router as transactions_router

from . import service
from .models import (
    CategoryChangeIn,
    CategoryOption,
    ManualTransactionCreate,
    ManualTransactionUpdate,
    TransactionList,
    TransactionRow,
)

router = APIRouter()
router.include_router(accounts_router)
router.include_router(categories_router)
router.include_router(transactions_router)
router.include_router(cashflow_router)
router.include_router(fixed_costs_router)
router.include_router(alerts_router)
router.include_router(import_router)

# ---- rotas v2 (/api/v1/ledger/*) — AD-15 ----
v2 = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])


@v2.get("/transactions", response_model=TransactionList)
async def list_transactions(
    user: AuthUser,
    db: Db,
    periodo: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionList:
    try:
        month = parse_periodo(periodo)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."},
        ) from None
    return await service.list_transactions(db, month, limit, offset)


@v2.patch("/transactions/{transaction_id}/category", response_model=TransactionRow)
async def change_category(
    transaction_id: str, body: CategoryChangeIn, user: AuthUser, db: Db
) -> TransactionRow:
    try:
        row = await service.set_category_manual(db, transaction_id, body.category_id)
    except LookupError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "categoria_inexistente", "message": "Categoria não existe."},
        ) from None
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "transacao_inexistente", "message": "Transação não encontrada."},
        )
    return row


@v2.get("/categories", response_model=list[CategoryOption])
async def list_category_options(
    user: AuthUser, db: Db, incluir_arquivadas: bool = False
) -> list[CategoryOption]:
    return await service.category_options(db, incluir_arquivadas)


_IMPORTED = {
    "error": "transacao_importada",
    "message": "Transação importada só muda de categoria.",
}
_NOT_FOUND = {"error": "transacao_inexistente", "message": "Transação não encontrada."}
_BAD_CATEGORY = {"error": "categoria_inexistente", "message": "Categoria não existe."}
_ZERO = {"error": "valor_zero", "message": "Informe um valor diferente de zero."}


@v2.post("/transactions", response_model=TransactionRow, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction(
    body: ManualTransactionCreate, user: AuthUser, db: Db
) -> TransactionRow:
    try:
        return await service.create_manual(db, body)
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _ZERO) from None


@v2.patch("/transactions/{transaction_id}", response_model=TransactionRow)
async def update_transaction(
    transaction_id: str, body: ManualTransactionUpdate, user: AuthUser, db: Db
) -> TransactionRow:
    try:
        row = await service.update_transaction(db, transaction_id, body)
    except service.ImportedTransactionError:
        raise HTTPException(status.HTTP_409_CONFLICT, _IMPORTED) from None
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _ZERO) from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return row


@v2.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_transaction(transaction_id: str, user: AuthUser, db: Db) -> None:
    try:
        found = await service.delete_manual(db, transaction_id)
    except service.ImportedTransactionError:
        raise HTTPException(status.HTTP_409_CONFLICT, _IMPORTED) from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)


router.include_router(v2)
