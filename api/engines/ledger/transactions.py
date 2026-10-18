"""CRUD de transações + validação + filtros/paginação (STORY-01-03).

amount: positivo = receita, negativo = despesa (nunca zero). account_id deve
existir (FK → 422). Lista paginada com filtros from/to/category/account_id.
NUMERIC(15,2) no banco; a API transporta float (cálculos autoritativos ficam em
SQL — ver view monthly_summary).
"""

import datetime
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from auth.dependencies import get_current_user
from db.connection import get_db
from engines.common.numbers import as_decimal
from engines.ledger import service as ledger_service
from engines.ledger.categories import CategoryKind
from engines.ledger.suggest import suggest_category

router = APIRouter(prefix="/api/v1/transactions", tags=["ledger:transactions"])

AuthUser = Annotated[dict[str, str], Depends(get_current_user)]
Db = Annotated[asyncpg.Connection, Depends(get_db)]


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    date: datetime.date
    amount: float
    category: str = Field(min_length=1)
    kind: CategoryKind | None = None  # ignorado desde a Story 2.5: o kind vem do grupo
    description: str | None = None
    is_recurring: bool = False
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("amount não pode ser zero (positivo=receita, negativo=despesa)")
        return v


class TransactionUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    date: datetime.date | None = None
    amount: float | None = None
    category: str | None = Field(default=None, min_length=1)
    kind: CategoryKind | None = None
    description: str | None = None
    is_recurring: bool | None = None
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v: float | None) -> float | None:
        if v is not None and v == 0:
            raise ValueError("amount não pode ser zero")
        return v


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    date: str
    amount: float
    category: str
    kind: str
    description: str | None
    is_recurring: bool
    external_id: str | None
    notes: str | None


class TransactionList(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
    total_income: float  # soma das receitas (kind=income) do conjunto filtrado
    total_expense: float  # soma das despesas/consumo (kind=expense, magnitude)
    total_invested: float  # aportes líquidos (kind=investment, magnitude)
    total_transfer: float  # soma líquida (com sinal) das transferências (kind=transfer) — ≈0
    transfer_count: int  # nº de lançamentos kind=transfer no conjunto filtrado


_COLUMNS = (
    "id, account_id, date, amount, category, kind, description, is_recurring, external_id, notes"
)


def _to_response(row: asyncpg.Record) -> TransactionResponse:
    return TransactionResponse(
        id=str(row["id"]),
        account_id=str(row["account_id"]),
        date=row["date"].isoformat(),
        amount=float(row["amount"]),
        category=row["category"],
        kind=row["kind"],
        description=row["description"],
        is_recurring=row["is_recurring"],
        external_id=row["external_id"],
        notes=row["notes"],
    )


async def _category_id(db: asyncpg.Connection, name: str) -> str:
    """Categoria escolhida pelo nome (as telas v1 mandam o nome da lista do banco). Story 2.5: a
    transação sempre tem uma subcategoria existente; o `kind` vem do grupo dela (AD-6)."""
    found = await db.fetchval(
        "SELECT id FROM categories WHERE name = $1 OR lower(name) = lower($1) "
        "ORDER BY (name = $1) DESC LIMIT 1",
        name,
    )
    if found is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"error": "categoria_inexistente", "message": f'Categoria "{name}" não existe.'},
        )
    return str(found)


@router.get("", response_model=TransactionList)
async def list_transactions(
    user: AuthUser,
    db: Db,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    from_: Annotated[datetime.date | None, Query(alias="from")] = None,
    to: Annotated[datetime.date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionList:
    where = (
        "WHERE ($1::uuid IS NULL OR account_id = $1) "
        "AND ($2::text IS NULL OR category = $2) "
        "AND ($3::date IS NULL OR date >= $3) "
        "AND ($4::date IS NULL OR date <= $4)"
    )
    agg = await db.fetchrow(
        "SELECT count(*) AS total, "
        "COALESCE(SUM(amount) FILTER (WHERE kind = 'income'), 0) AS income, "
        "COALESCE(SUM(-amount) FILTER (WHERE kind = 'expense'), 0) AS expense, "
        "COALESCE(SUM(-amount) FILTER (WHERE kind = 'investment'), 0) AS invested, "
        "COALESCE(SUM(amount) FILTER (WHERE kind = 'transfer'), 0) AS transfer_net, "
        "COUNT(*) FILTER (WHERE kind = 'transfer') AS transfer_count "
        f"FROM transactions {where}",
        account_id,
        category,
        from_,
        to,
    )
    rows = await db.fetch(
        f"SELECT {_COLUMNS} FROM transactions {where} "
        "ORDER BY date DESC, created_at DESC LIMIT $5 OFFSET $6",
        account_id,
        category,
        from_,
        to,
        limit,
        offset,
    )
    return TransactionList(
        items=[_to_response(r) for r in rows],
        total=agg["total"],
        limit=limit,
        offset=offset,
        total_income=float(agg["income"]),
        total_expense=float(agg["expense"]),
        total_invested=float(agg["invested"]),
        total_transfer=float(agg["transfer_net"]),
        transfer_count=int(agg["transfer_count"]),
    )


class SuggestionOut(BaseModel):
    transaction_id: uuid.UUID
    date: datetime.date
    description: str
    amount: float
    suggested_category: str
    score: float


@router.get("/suggestions", response_model=list[SuggestionOut])
async def suggest_categories(
    user: AuthUser,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SuggestionOut]:
    """Sugere categoria para despesas em 'outros', por similaridade com o histórico
    já categorizado. Híbrido: o usuário confirma (PUT na transação) e pode salvar um
    match_pattern depois. Não altera nada — só propõe."""
    hist = await db.fetch(
        "SELECT description, category FROM transactions "
        "WHERE kind = 'expense' AND category <> 'outros' "
        "AND description IS NOT NULL AND description <> '' "
        "ORDER BY date DESC LIMIT 2000"
    )
    history = [(r["description"], r["category"]) for r in hist]
    pending = await db.fetch(
        "SELECT id, date, description, amount FROM transactions "
        "WHERE kind = 'expense' AND category = 'outros' "
        "AND description IS NOT NULL AND description <> '' "
        "ORDER BY date DESC LIMIT $1",
        limit,
    )
    out: list[SuggestionOut] = []
    for r in pending:
        sug = suggest_category(r["description"], history)
        if sug is None:
            continue
        out.append(
            SuggestionOut(
                transaction_id=r["id"],
                date=r["date"],
                description=r["description"],
                amount=float(r["amount"]),
                suggested_category=sug[0],
                score=round(sug[1], 3),
            )
        )
    return out


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreate, user: AuthUser, db: Db
) -> TransactionResponse:
    category_id = await _category_id(db, body.category)
    positive = body.amount > 0
    async with db.transaction():
        try:
            # Lançamento à mão (source manual, sem lote): entra "a classificar" e recebe a categoria
            # escolhida por categorize() — origem manual, confirmada (Story 2.5).
            tx_id = await db.fetchval(
                "INSERT INTO transactions "
                "(account_id, date, amount, category, category_id, kind, description, "
                "is_recurring, notes, source) "
                "VALUES ($1, $2, $3, $4, "
                "(SELECT id FROM categories WHERE key = $5), $6, $7, $8, $9, 'manual') "
                "RETURNING id",
                body.account_id,
                body.date,
                as_decimal(body.amount),
                "Entrada a classificar" if positive else "Saída a classificar",
                "sistema:entrada_a_classificar" if positive else "sistema:saida_a_classificar",
                "income" if positive else "expense",
                body.description,
                body.is_recurring,
                body.notes,
            )
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conta inexistente") from None
        await ledger_service.categorize(
            db,
            [ledger_service.CategoryChange(str(tx_id), category_id, "manual")],
            cause="inline_edit",
            review_status="confirmed",
        )
        row = await db.fetchrow(f"SELECT {_COLUMNS} FROM transactions WHERE id = $1", tx_id)
    return _to_response(row)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID, body: TransactionUpdate, user: AuthUser, db: Db
) -> TransactionResponse:
    # Story 2.5: os demais campos mudam aqui; categoria (e o kind do grupo) só por categorize().
    category_id = await _category_id(db, body.category) if body.category is not None else None
    async with db.transaction():
        try:
            row = await db.fetchrow(
                """
                UPDATE transactions SET
                  account_id = COALESCE($2, account_id),
                  date = COALESCE($3, date),
                  amount = COALESCE($4, amount),
                  description = COALESCE($5, description),
                  is_recurring = COALESCE($6, is_recurring),
                  notes = COALESCE($7, notes)
                WHERE id = $1
                RETURNING id
                """,
                transaction_id,
                body.account_id,
                body.date,
                as_decimal(body.amount),
                body.description,
                body.is_recurring,
                body.notes,
            )
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "conta inexistente") from None
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
        if category_id is not None:
            await ledger_service.categorize(
                db,
                [ledger_service.CategoryChange(str(transaction_id), category_id, "manual")],
                cause="inline_edit",
                review_status="confirmed",
            )
        row = await db.fetchrow(
            f"SELECT {_COLUMNS} FROM transactions WHERE id = $1", transaction_id
        )
    return _to_response(row)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: uuid.UUID, user: AuthUser, db: Db) -> None:
    result = await db.execute("DELETE FROM transactions WHERE id = $1", transaction_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transação não encontrada")
