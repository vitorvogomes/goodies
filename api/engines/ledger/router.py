"""Agregador de rotas do Ledger Engine (m1).

Cada sub-módulo expõe seu próprio APIRouter com prefixo /api/v1/...; este
agregador é incluído uma vez no main.py. Novos sub-routers (transactions,
cashflow, ...) entram aqui conforme as stories avançam.
"""

from fastapi import APIRouter

from engines.ledger.accounts import router as accounts_router
from engines.ledger.categories import router as categories_router
from engines.ledger.transactions import router as transactions_router

router = APIRouter()
router.include_router(accounts_router)
router.include_router(categories_router)
router.include_router(transactions_router)
