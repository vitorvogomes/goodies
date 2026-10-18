"""Agregador de rotas do Ledger Engine (m1).

Cada sub-módulo expõe seu próprio APIRouter com prefixo /api/v1/...; este
agregador é incluído uma vez no main.py. Novos sub-routers (transactions,
cashflow, ...) entram aqui conforme as stories avançam.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from engines.common.dates import parse_periodo
from engines.common.deps import AuthUser, Db
from engines.common.models import Uuid
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
    CategoryGroupNode,
    CategoryNode,
    CategoryOption,
    GroupCreate,
    GroupUpdate,
    ManualTransactionCreate,
    ManualTransactionUpdate,
    ReapplyIn,
    ReapplyPreview,
    ReapplyResult,
    ReviewConfirmIn,
    ReviewConfirmOut,
    ReviewList,
    RuleCreate,
    RuleCreated,
    RulePreviewIn,
    RulePreviewOut,
    RuleProposal,
    RuleProposalIn,
    RuleRow,
    RuleUpdate,
    SubcategoryCreate,
    SubcategoryUpdate,
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
_INVALID_PERIOD = {"error": "periodo_invalido", "message": "Período inválido (use AAAA-MM)."}


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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INVALID_PERIOD) from None
    return await service.list_transactions(db, month, limit, offset)


@v2.patch("/transactions/{transaction_id}/category", response_model=TransactionRow)
async def change_category(
    transaction_id: Uuid, body: CategoryChangeIn, user: AuthUser, db: Db
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
_BAD_ACCOUNT = {"error": "conta_inexistente", "message": "Conta não existe."}
_ZERO = {"error": "valor_zero", "message": "Informe um valor diferente de zero."}


@v2.post("/transactions", response_model=TransactionRow, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction(
    body: ManualTransactionCreate, user: AuthUser, db: Db
) -> TransactionRow:
    try:
        return await service.create_manual(db, body)
    except service.UnknownAccountError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_ACCOUNT) from None
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _ZERO) from None


@v2.patch("/transactions/{transaction_id}", response_model=TransactionRow)
async def update_transaction(
    transaction_id: Uuid, body: ManualTransactionUpdate, user: AuthUser, db: Db
) -> TransactionRow:
    try:
        row = await service.update_transaction(db, transaction_id, body)
    except service.ImportedTransactionError:
        raise HTTPException(status.HTTP_409_CONFLICT, _IMPORTED) from None
    except service.UnknownAccountError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_ACCOUNT) from None
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _ZERO) from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return row


@v2.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_transaction(transaction_id: Uuid, user: AuthUser, db: Db) -> None:
    try:
        found = await service.delete_manual(db, transaction_id)
    except service.ImportedTransactionError:
        raise HTTPException(status.HTTP_409_CONFLICT, _IMPORTED) from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)


# ---- Ajustes › Categorias (Story 2.9) ----


def _rule_error(exc: service.CategoryRuleError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, {"error": exc.code, "message": exc.message})


@v2.get("/category-tree", response_model=list[CategoryGroupNode])
async def category_tree(
    user: AuthUser, db: Db, incluir_arquivadas: bool = False
) -> list[CategoryGroupNode]:
    return await service.category_tree(db, incluir_arquivadas)


@v2.post("/category-groups", status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreate, user: AuthUser, db: Db) -> dict[str, str]:
    try:
        return {"id": await service.create_group(db, body)}
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None


@v2.patch("/category-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_group(group_id: Uuid, body: GroupUpdate, user: AuthUser, db: Db) -> None:
    try:
        found = await service.update_group(db, group_id, body)
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None
    if not found:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "grupo_inexistente", "message": "Grupo não existe."},
        )


@v2.post("/categories", response_model=CategoryNode, status_code=status.HTTP_201_CREATED)
async def create_category(body: SubcategoryCreate, user: AuthUser, db: Db) -> CategoryNode:
    try:
        return await service.create_category(db, body)
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None


@v2.patch("/categories/{category_id}", response_model=CategoryNode)
async def update_category(
    category_id: Uuid, body: SubcategoryUpdate, user: AuthUser, db: Db
) -> CategoryNode:
    try:
        node = await service.update_category(db, category_id, body)
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _BAD_CATEGORY)
    return node


@v2.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: Uuid, user: AuthUser, db: Db) -> None:
    try:
        found = await service.delete_category(db, category_id)
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _BAD_CATEGORY)


# ---- Ajustes › Regras e reaplicação (Story 2.10) ----
_RULE_NOT_FOUND = {"error": "regra_inexistente", "message": "Regra não existe."}
_BAD_PERIOD = {"error": "periodo_invalido", "message": "O fim do período vem antes do início."}


@v2.get("/rules", response_model=list[RuleRow])
async def list_rules(user: AuthUser, db: Db) -> list[RuleRow]:
    return await service.list_rules(db)


@v2.patch("/rules/{rule_id}", response_model=RuleRow)
async def update_rule(rule_id: Uuid, body: RuleUpdate, user: AuthUser, db: Db) -> RuleRow:
    try:
        row = await service.update_rule(db, rule_id, body)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "condicao_vazia", "message": "Informe o texto da condição."},
        ) from None
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None
    except service.CategoryRuleError as exc:
        raise _rule_error(exc) from None
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "regra_inexistente", "message": "Regra não existe."},
        )
    return row


@v2.post("/rules/propose", response_model=RuleProposal)
async def propose_rule(body: RuleProposalIn, user: AuthUser, db: Db) -> RuleProposal:
    proposal = await service.propose_rule(db, body)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return proposal


@v2.post("/rules", response_model=RuleCreated, status_code=status.HTTP_201_CREATED)
async def create_rule(body: RuleCreate, user: AuthUser, db: Db) -> RuleCreated:
    try:
        return await service.create_rule(db, body)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "condicao_vazia", "message": "Informe o texto da condição."},
        ) from None
    except LookupError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_CATEGORY) from None


@v2.post("/rules/preview", response_model=RulePreviewOut)
async def preview_rule(body: RulePreviewIn, user: AuthUser, db: Db) -> RulePreviewOut:
    return await service.preview_rule(db, body)


@v2.post("/rules/reapply/preview", response_model=ReapplyPreview)
async def preview_reapply(body: ReapplyIn, user: AuthUser, db: Db) -> ReapplyPreview:
    try:
        return await service.preview_reapply(db, body)
    except service.ReversedPeriodError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_PERIOD) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INVALID_PERIOD) from None


@v2.post("/rules/reapply", response_model=ReapplyResult)
async def reapply_rules(body: ReapplyIn, user: AuthUser, db: Db) -> ReapplyResult:
    try:
        return await service.reapply_rules(db, body)
    except service.ReversedPeriodError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _BAD_PERIOD) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INVALID_PERIOD) from None


# ---- Revisão de transações (Story 3.10) ----


@v2.get("/review", response_model=ReviewList)
async def review_list(user: AuthUser, db: Db, lote: Uuid | None = None) -> ReviewList:
    return await service.review_list(db, lote)


@v2.post("/review/confirm", response_model=ReviewConfirmOut)
async def review_confirm(body: ReviewConfirmIn, user: AuthUser, db: Db) -> ReviewConfirmOut:
    try:
        return await service.review_confirm(db, body)
    except service.UncategorizedError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"error": "sem_categoria", "message": "Escolha a categoria ou desmarque a linha."},
        ) from None
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND) from None


router.include_router(v2)
