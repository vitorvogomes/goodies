"""Serviço do Ledger: avaliação de alertas v1 (STORY-01-08, puros) e `categorize()`, o caminho
único de mudança de categoria (Story 2.5 — AD-6).

As funções de alerta recebem `today` injetado -> determinísticas e testáveis sem relógio nem DB.
"""

import calendar
import datetime
import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import asyncpg

from engines.common.alerts import (
    Alert,
    AlertAction,
    AlertContext,
    LegacyAlert,
    brl,
    fingerprint,
)
from engines.common.dates import parse_periodo
from engines.common.month_status import month_status

from . import queries
from .calc import (
    BalanceInterval,
    Movement,
    Rule,
    best_rule,
    chained_check,
    computed_balance,
    month_result,
    opening_balance,
    savings_rate,
)
from .models import (
    DEFAULT_ROLE,
    GROUP_KIND_LABEL,
    KIND_LABEL,
    ROLE_LABEL,
    ROLES_BY_KIND,
    BalanceCandidate,
    BalanceCandidates,
    CategoryGroupNode,
    CategoryNode,
    CategoryOption,
    GroupCreate,
    GroupUpdate,
    ManualTransactionCreate,
    ManualTransactionUpdate,
    Origin,
    ReapplyChange,
    ReapplyIn,
    ReapplyPreview,
    ReapplyResult,
    ReviewConfirmIn,
    ReviewConfirmOut,
    ReviewItem,
    ReviewList,
    ReviewMonth,
    RuleCreate,
    RuleCreated,
    RuleMatch,
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


@dataclass
class FixedCostDue:
    name: str
    amount: float
    due_day: int
    category: str


@dataclass
class MonthCategoryTotal:
    month: datetime.date  # primeiro dia do mês
    category: str
    total: float  # magnitude da despesa (positivo)


def _occurrence(year: int, month: int, due_day: int) -> datetime.date:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(due_day, last))


def _next_occurrence(due_day: int, today: datetime.date) -> datetime.date:
    this_month = _occurrence(today.year, today.month, due_day)
    if this_month >= today:
        return this_month
    if today.month == 12:
        return _occurrence(today.year + 1, 1, due_day)
    return _occurrence(today.year, today.month + 1, due_day)


def upcoming_due_alerts(
    items: list[FixedCostDue], today: datetime.date, horizon: int = 5
) -> list[LegacyAlert]:
    """Custos fixos com vencimento nos próximos `horizon` dias."""
    alerts: list[LegacyAlert] = []
    for fc in items:
        days_until = (_next_occurrence(fc.due_day, today) - today).days
        if 0 <= days_until <= horizon:
            alerts.append(
                LegacyAlert(
                    type="fixed_cost_due",
                    severity="warning",
                    title="Custo fixo vencendo",
                    message=f"{fc.name} vence em {days_until} dia(s) (dia {fc.due_day})",
                    data={
                        "name": fc.name,
                        "amount": round(fc.amount, 2),
                        "due_day": fc.due_day,
                        "days_until": days_until,
                    },
                )
            )
    return alerts


def _month_minus(month_start: datetime.date, n: int) -> datetime.date:
    total = (month_start.year * 12 + (month_start.month - 1)) - n
    return datetime.date(total // 12, total % 12 + 1, 1)


def category_overspend_alerts(
    rows: list[MonthCategoryTotal], today: datetime.date, factor: float = 1.2
) -> list[LegacyAlert]:
    """Categorias cujo gasto do mês atual passa de `factor`x a média dos 3 meses anteriores."""
    current = datetime.date(today.year, today.month, 1)
    prev_months = {_month_minus(current, n) for n in (1, 2, 3)}

    current_by_cat: dict[str, float] = {}
    prev_by_cat: dict[str, float] = {}
    for r in rows:
        if r.month == current:
            current_by_cat[r.category] = current_by_cat.get(r.category, 0.0) + r.total
        elif r.month in prev_months:
            prev_by_cat[r.category] = prev_by_cat.get(r.category, 0.0) + r.total

    alerts: list[LegacyAlert] = []
    for category, current_total in current_by_cat.items():
        if category not in prev_by_cat:
            continue
        avg = prev_by_cat[category] / 3  # meses ausentes contam como 0
        if avg > 0 and current_total > factor * avg:
            pct = round((current_total / avg - 1) * 100)
            alerts.append(
                LegacyAlert(
                    type="category_overspend",
                    severity="warning",
                    title="Categoria acima da média",
                    message=(
                        f"Categoria '{category}' está {pct}% acima da média dos últimos 3 meses"
                    ),
                    data={
                        "category": category,
                        "current": round(current_total, 2),
                        "avg_3m": round(avg, 2),
                        "pct_above": pct,
                    },
                )
            )
    return alerts


# --------------------------------------------------------------------------------------------
# Providers da Central de avisos (AD-10 — Story 3.1), registrados em `main.py`
# --------------------------------------------------------------------------------------------


async def fixed_cost_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Custo fixo vencendo em até 5 dias: "{Custo} vence em {dd/mm/aaaa}." (catálogo da UX)."""
    alerts: list[Alert] = []
    for r in await conn.fetch(queries.ACTIVE_FIXED_COSTS):
        due = _next_occurrence(r["due_day"], ctx.today)
        if (due - ctx.today).days > 5:
            continue
        alerts.append(
            Alert(
                key=f"custo_fixo_vencendo:{r['id']}",
                fingerprint=fingerprint(due),
                severity="aviso",
                message=f"{r['name']} vence em {due:%d/%m/%Y}.",
                action=AlertAction(label="Ver custos fixos", route="/ajustes/custos-fixos"),
                as_of=ctx.today,
            )
        )
    return alerts


async def overspend_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Consumo do mês corrente acima de 120% da média dos 3 meses anteriores, por subcategoria."""
    rows = await conn.fetch(queries.CONSUMPTION_BY_CATEGORY, ctx.today)
    ids = {r["label"]: str(r["category_id"]) for r in rows}
    totals = [
        MonthCategoryTotal(month=r["month"], category=r["label"], total=float(r["total"]))
        for r in rows
    ]
    periodo = f"{ctx.today:%Y-%m}"
    return [
        Alert(
            key=f"gasto_acima_da_media:{ids[str(a.data['category'])]}",
            fingerprint=fingerprint(periodo),
            severity="aviso",
            message=(
                f"{a.data['category']} em {brl(float(a.data['current']))}, "
                f"{a.data['pct_above']}% acima da média de 3 meses."
            ),
            action=AlertAction(
                label="Ver transações",
                route="/caixa/transacoes",
                params={"periodo": periodo, "categoria": ids[str(a.data["category"])]},
            ),
            as_of=ctx.today,
        )
        for a in category_overspend_alerts(totals, ctx.today)
    ]


# --------------------------------------------------------------------------------------------
# Categorização por um caminho só (Story 2.5 — AD-6)
# --------------------------------------------------------------------------------------------

Source = Literal["rule", "suggestion", "manual"]
Cause = Literal[
    "import", "review", "inline_edit", "rule_created", "reapply", "move", "migration", "undo"
]
TransactionsChangedHook = Callable[[asyncpg.Connection, list[str]], Awaitable[None]]

_hooks: list[TransactionsChangedHook] = []


def register_on_transactions_changed(hook: TransactionsChangedHook) -> None:
    """Engines de cima (portfolio) registram a derivação em `main.py` (AD-1/AD-6)."""
    _hooks.append(hook)


def unregister_on_transactions_changed(hook: TransactionsChangedHook) -> None:
    if hook in _hooks:
        _hooks.remove(hook)


_deleting_hooks: list[TransactionsChangedHook] = []


def register_on_transactions_deleting(hook: TransactionsChangedHook) -> None:
    """Antes de apagar transações: quem deriva delas (portfolio) remove o que derivou (a FK
    `asset_operations.transaction_id` é RESTRICT)."""
    if hook not in _deleting_hooks:
        _deleting_hooks.append(hook)


async def run_deleting_hooks(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    for hook in _deleting_hooks:
        await hook(conn, transaction_ids)


def clear_transaction_hooks() -> None:
    _hooks.clear()


async def run_transaction_hooks(conn: asyncpg.Connection, transaction_ids: list[str]) -> None:
    for hook in _hooks:
        await hook(conn, transaction_ids)


@dataclass(frozen=True)
class CategoryChange:
    transaction_id: str
    category_id: str
    source: Source
    rule_id: str | None = None


@dataclass
class CategorizeResult:
    changed: list[str] = field(default_factory=list)
    kept_manual: list[str] = field(default_factory=list)


async def load_rules(conn: asyncpg.Connection) -> list[Rule]:
    return [
        Rule(
            pattern=r["pattern"],
            direction=r["direction"],
            category_id=str(r["category_id"]),
            category_name=r["category_name"],
            kind=r["kind"],
            rule_id=str(r["id"]),
            created_at=r["created_at"],
        )
        for r in await queries.active_rules(conn)
    ]


async def categorize(
    conn: asyncpg.Connection,
    changes: Sequence[CategoryChange],
    *,
    cause: Cause,
    batch_id: str | None = None,
    review_status: Literal["pending", "confirmed"] | None = None,
    fire_hooks: bool = True,
) -> CategorizeResult:
    """Único caminho de mudança de categoria (AD-6). Roda na transação de quem chama.

    Grava `category_id`, a cópia de `kind` do grupo, a coluna de texto (esquema duplo até a 10.6),
    `category_source` e a regra; registra o evento; marca o mês sujo; chama os hooks. Categoria
    `manual` nunca é sobrescrita por regra ou sugestão.
    """
    result = CategorizeResult()
    if not changes:
        return result
    tx_ids = [c.transaction_id for c in changes]
    state = {str(r["id"]): r for r in await conn.fetch(queries.TX_STATE, tx_ids)}
    cats = {
        str(r["id"]): r
        for r in await conn.fetch(queries.CATEGORY_INFO, list({c.category_id for c in changes}))
    }
    months: set[date] = set()
    for ch in changes:
        current = state.get(ch.transaction_id)
        if current is None:
            raise LookupError(f"transação inexistente: {ch.transaction_id}")
        cat = cats.get(ch.category_id)
        if cat is None:
            raise LookupError(f"categoria inexistente: {ch.category_id}")
        if current["category_source"] == "manual" and ch.source != "manual":
            result.kept_manual.append(ch.transaction_id)
            continue
        before = str(current["category_id"]) if current["category_id"] else None
        rule_id = ch.rule_id if ch.source == "rule" else None
        if (
            cause != "move"
            and before == ch.category_id
            and current["category_source"] == ch.source
            and (review_status is None or review_status == current["review_status"])
        ):
            continue  # nada muda: sem evento
        await conn.execute(
            queries.APPLY_CATEGORY,
            ch.transaction_id,
            ch.category_id,
            cat["name"],
            cat["kind"],
            ch.source,
            rule_id,
            review_status,
        )
        await conn.execute(
            queries.INSERT_EVENT,
            ch.transaction_id,
            before,
            ch.category_id,
            ch.source,
            cause,
            batch_id,
            rule_id,
        )
        result.changed.append(ch.transaction_id)
        months.add(current["date"].replace(day=1))
    port = month_status()
    for month in sorted(months):
        await port.mark_dirty(conn, month)
    if fire_hooks and result.changed:
        await run_transaction_hooks(conn, list(result.changed))
    return result


async def monthly_savings(
    conn: asyncpg.Connection, months: Sequence[date] | None = None
) -> dict[date, Decimal | None]:
    """Taxa de poupança (fração) por mês pela função única de `ledger/calc` (Story 2.6, AD-7).
    Mês sem receita do trabalho → None."""
    by_month: dict[date, list[Movement]] = {}
    for r in await queries.month_movements(conn, months):
        by_month.setdefault(r["month"], []).append(Movement(r["amount"], r["kind"], r["role"]))
    return {m: savings_rate(mv) for m, mv in sorted(by_month.items())}


# --------------------------------------------------------------------------------------------
# Caixa › Transações (Story 2.7)
# --------------------------------------------------------------------------------------------


def to_row(r: asyncpg.Record) -> TransactionRow:
    return TransactionRow(
        id=str(r["id"]),
        date=r["date"],
        description=r["description"],
        amount=r["amount"],
        kind=r["kind"],
        kind_label=KIND_LABEL.get(r["kind"], r["kind"]),
        category_id=str(r["category_id"]),
        category_name=r["category_name"],
        category_key=r["category_key"],
        group_name=r["group_name"],
        category_source=r["category_source"],
        review_status=r["review_status"],
        payer=r["payer"],
        account_id=str(r["account_id"]),
        account_name=r["account_name"],
        source=r["source"],
        batch_id=str(r["batch_id"]) if r["batch_id"] else None,
        file_name=r["file_name"],
        rule_pattern=r["rule_pattern"],
    )


async def list_transactions(
    conn: asyncpg.Connection, month: date, limit: int, offset: int
) -> TransactionList:
    end = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    rows, total = await queries.transactions_page(conn, month, end, limit, offset)
    return TransactionList(items=[to_row(r) for r in rows], total=total, limit=limit, offset=offset)


async def set_category_manual(
    conn: asyncpg.Connection, tx_id: str, category_id: str
) -> TransactionRow | None:
    """Correção na linha: categorize() com origem manual, confirmada (Story 2.7)."""
    if not await queries.category_exists(conn, category_id):
        raise LookupError("categoria")
    async with conn.transaction():
        if await queries.transaction_row(conn, tx_id) is None:
            return None
        await categorize(
            conn,
            [CategoryChange(tx_id, category_id, "manual")],
            cause="inline_edit",
            review_status="confirmed",
        )
    row = await queries.transaction_row(conn, tx_id)
    return to_row(row) if row is not None else None


async def category_options(
    conn: asyncpg.Connection, include_archived: bool = False
) -> list[CategoryOption]:
    return [
        CategoryOption(
            id=str(r["id"]),
            key=r["key"],
            name=r["name"],
            label=f"{r['group_name']} › {r['name']}",
            group_key=r["group_key"],
            group_name=r["group_name"],
            kind=r["kind"],
            role=r["role"],
            is_active=r["is_active"],
        )
        for r in await queries.category_options(conn, include_archived)
    ]


# --------------------------------------------------------------------------------------------
# Lançamento manual (Story 2.8)
# --------------------------------------------------------------------------------------------


class ImportedTransactionError(Exception):
    """Transação importada: só a categoria muda."""


async def mark_months(conn: asyncpg.Connection, *days: date) -> None:
    port = month_status()
    for month in sorted({d.replace(day=1) for d in days}):
        await port.mark_dirty(conn, month)


class UnknownAccountError(LookupError):
    """Conta inexistente no lançamento manual."""


async def _check_account(conn: asyncpg.Connection, account_id: str | None) -> None:
    if account_id is not None and not await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM accounts WHERE id = $1::uuid)", account_id
    ):
        raise UnknownAccountError("conta")


async def create_manual(conn: asyncpg.Connection, body: ManualTransactionCreate) -> TransactionRow:
    if body.amount == 0:
        raise ValueError("valor")
    await _check_account(conn, body.account_id)
    if not await queries.category_exists(conn, body.category_id):
        raise LookupError("categoria")
    positive = body.amount > 0
    async with conn.transaction():
        tx_id = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
            "description, source) VALUES ($1::uuid, $2, $3, $4, "
            "(SELECT id FROM categories WHERE key = $5), $6, $7, 'manual') RETURNING id",
            body.account_id,
            body.date,
            body.amount,
            "Entrada a classificar" if positive else "Saída a classificar",
            "sistema:entrada_a_classificar" if positive else "sistema:saida_a_classificar",
            "income" if positive else "expense",
            body.description,
        )
        await categorize(
            conn,
            [CategoryChange(str(tx_id), body.category_id, "manual")],
            cause="inline_edit",
            review_status="confirmed",
        )
        await mark_months(conn, body.date)
        row = await queries.transaction_row(conn, str(tx_id))
    assert row is not None
    return to_row(row)


async def update_transaction(
    conn: asyncpg.Connection, tx_id: str, body: ManualTransactionUpdate
) -> TransactionRow | None:
    """Manual muda tudo; importada só a categoria (Story 2.8)."""
    if body.category_id is not None and not await queries.category_exists(conn, body.category_id):
        raise LookupError("categoria")
    if body.amount is not None and body.amount == 0:
        raise ValueError("valor")
    await _check_account(conn, body.account_id)
    fields = body.model_dump(exclude_none=True, exclude={"category_id"})
    async with conn.transaction():
        current = await queries.tx_source(conn, tx_id)
        if current is None:
            return None
        if fields and current["source"] != "manual":
            raise ImportedTransactionError
        if fields:
            await conn.execute(
                "UPDATE transactions SET account_id = COALESCE($2::uuid, account_id), "
                "date = COALESCE($3, date), amount = COALESCE($4, amount), "
                "description = COALESCE($5, description) WHERE id = $1::uuid",
                tx_id,
                body.account_id,
                body.date,
                body.amount,
                body.description,
            )
            await mark_months(conn, current["date"], body.date or current["date"])
        if body.category_id is not None:
            await categorize(
                conn,
                [CategoryChange(tx_id, body.category_id, "manual")],
                cause="inline_edit",
                review_status="confirmed",
            )
        row = await queries.transaction_row(conn, tx_id)
    return to_row(row) if row is not None else None


async def delete_manual(conn: asyncpg.Connection, tx_id: str) -> bool:
    async with conn.transaction():
        current = await queries.tx_source(conn, tx_id)
        if current is None:
            return False
        if current["source"] != "manual":
            raise ImportedTransactionError
        await run_deleting_hooks(conn, [tx_id])
        await conn.execute("DELETE FROM transactions WHERE id = $1::uuid", tx_id)
        await mark_months(conn, current["date"])
    return True


# --------------------------------------------------------------------------------------------
# Ajustes › Categorias (Story 2.9)
# --------------------------------------------------------------------------------------------


class CategoryRuleError(Exception):
    """Regra de produto violada; `code` vira o `error` do contrato HTTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _node(r: asyncpg.Record) -> CategoryNode:
    return CategoryNode(
        id=str(r["id"]),
        key=r["key"],
        name=r["name"],
        group_id=str(r["group_id"]),
        kind=r["kind"],
        role=r["role"],
        role_label=ROLE_LABEL.get(r["role"], r["role"]),
        is_active=r["is_active"],
        is_system=r["is_system"],
        transaction_count=int(r["transaction_count"]),
    )


async def category_tree(
    conn: asyncpg.Connection, include_archived: bool = False
) -> list[CategoryGroupNode]:
    groups = await conn.fetch(queries.TREE_GROUPS, include_archived)
    cats = [_node(r) for r in await conn.fetch(queries.TREE_CATEGORIES, include_archived)]
    out = []
    for g in groups:
        children = [c for c in cats if c.group_id == str(g["id"])]
        out.append(
            CategoryGroupNode(
                id=str(g["id"]),
                key=g["key"],
                name=g["name"],
                kind=g["kind"],
                kind_label=GROUP_KIND_LABEL[g["kind"]],
                is_active=g["is_active"],
                is_system=g["is_system"],
                transaction_count=sum(c.transaction_count for c in children),
                categories=children,
            )
        )
    return out


async def create_group(conn: asyncpg.Connection, body: GroupCreate) -> str:
    if await conn.fetchval(
        "SELECT 1 FROM category_groups WHERE lower(name) = lower($1)", body.name
    ):
        raise CategoryRuleError("grupo_existente", "Já existe um grupo com esse nome.")
    gid = await conn.fetchval(
        "INSERT INTO category_groups (key, name, kind) "
        "VALUES ('grupo:' || left(md5(gen_random_uuid()::text), 12), $1, $2) RETURNING id",
        body.name.strip(),
        body.kind,
    )
    return str(gid)


async def update_group(conn: asyncpg.Connection, group_id: str, body: GroupUpdate) -> bool:
    async with conn.transaction():
        g = await conn.fetchrow(
            "SELECT id, kind, is_system FROM category_groups WHERE id = $1::uuid FOR UPDATE",
            group_id,
        )
        if g is None:
            return False
        if g["is_system"]:
            raise CategoryRuleError("grupo_de_sistema", "Grupo de sistema não se edita.")
        if body.kind is not None and body.kind != g["kind"]:
            used = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM transactions t JOIN categories c "
                "ON c.id = t.category_id WHERE c.group_id = $1::uuid)",
                group_id,
            )
            if used:
                raise CategoryRuleError(
                    "tipo_com_transacoes",
                    "O tipo de um grupo com transações não muda. Mova as subcategorias.",
                )
            await conn.execute(
                "UPDATE categories SET kind = $2, role = $3 WHERE group_id = $1::uuid",
                group_id,
                body.kind,
                DEFAULT_ROLE[body.kind],
            )
        await conn.execute(
            "UPDATE category_groups SET name = COALESCE($2, name), kind = COALESCE($3, kind), "
            "is_active = COALESCE($4, is_active) WHERE id = $1::uuid",
            group_id,
            body.name.strip() if body.name else None,
            body.kind,
            body.is_active,
        )
    return True


async def _category_row(conn: asyncpg.Connection, category_id: str) -> CategoryNode | None:
    row = await conn.fetchrow(queries.CATEGORY_ROW, category_id)
    return _node(row) if row is not None else None


def _check_role(role: str, kind: str) -> None:
    if role not in ROLES_BY_KIND[kind]:
        raise CategoryRuleError("papel_invalido", "Esse papel não vale para o tipo do grupo.")


async def create_category(conn: asyncpg.Connection, body: SubcategoryCreate) -> CategoryNode:
    g = await conn.fetchrow(
        "SELECT id, kind, is_system FROM category_groups WHERE id = $1::uuid", body.group_id
    )
    if g is None or g["is_system"]:
        raise CategoryRuleError("grupo_inexistente", "Escolha um grupo existente.")
    role = body.role or DEFAULT_ROLE[g["kind"]]
    _check_role(role, g["kind"])
    try:
        cid = await conn.fetchval(
            "INSERT INTO categories (name, kind, group_id, role, key) VALUES ($1, $2, $3, $4, "
            "'custom:' || left(md5(gen_random_uuid()::text), 12)) RETURNING id",
            body.name.strip(),
            g["kind"],
            g["id"],
            role,
        )
    except asyncpg.UniqueViolationError:
        raise CategoryRuleError(
            "categoria_existente", "Já existe uma categoria com esse nome."
        ) from None
    node = await _category_row(conn, str(cid))
    assert node is not None
    return node


async def update_category(
    conn: asyncpg.Connection, category_id: str, body: SubcategoryUpdate
) -> CategoryNode | None:
    async with conn.transaction():
        current = await _category_row(conn, category_id)
        if current is None:
            return None
        if current.is_system:
            raise CategoryRuleError("categoria_de_sistema", "Categoria de sistema não se edita.")
        target = None
        if body.group_id is not None and body.group_id != current.group_id:
            target = await conn.fetchrow(
                "SELECT id, kind, is_system FROM category_groups WHERE id = $1::uuid",
                body.group_id,
            )
            if target is None or target["is_system"]:
                raise CategoryRuleError("grupo_inexistente", "Escolha um grupo existente.")
        kind = target["kind"] if target is not None else current.kind
        # O papel escolhido vale; sem escolha, mudar de tipo leva ao papel padrão do novo tipo.
        role = body.role or (current.role if kind == current.kind else DEFAULT_ROLE[kind])
        _check_role(role, kind)
        if body.name is not None and body.name.strip() != current.name:
            try:
                await conn.execute(
                    "UPDATE categories SET name = $2 WHERE id = $1::uuid",
                    category_id,
                    body.name.strip(),
                )
            except asyncpg.UniqueViolationError:
                raise CategoryRuleError(
                    "categoria_existente", "Já existe uma categoria com esse nome."
                ) from None
            for sql in queries.RENAME_TEXT_COLUMNS:
                await conn.execute(sql, category_id, body.name.strip())
        await conn.execute(
            "UPDATE categories SET role = $2, is_active = COALESCE($3, is_active) "
            "WHERE id = $1::uuid",
            category_id,
            role,
            body.is_active,
        )
        if target is not None:
            await conn.execute(
                "UPDATE categories SET group_id = $2, kind = $3 WHERE id = $1::uuid",
                category_id,
                target["id"],
                kind,
            )
            if kind != current.kind:
                txs = await conn.fetch(
                    "SELECT id, category_source, category_rule_id FROM transactions "
                    "WHERE category_id = $1::uuid",
                    category_id,
                )
                await categorize(
                    conn,
                    [
                        CategoryChange(
                            str(t["id"]),
                            category_id,
                            t["category_source"],
                            str(t["category_rule_id"]) if t["category_rule_id"] else None,
                        )
                        for t in txs
                    ],
                    cause="move",
                )
        return await _category_row(conn, category_id)


async def delete_category(conn: asyncpg.Connection, category_id: str) -> bool:
    async with conn.transaction():
        current = await _category_row(conn, category_id)
        if current is None:
            return False
        if current.is_system:
            raise CategoryRuleError("categoria_de_sistema", "Categoria de sistema não se apaga.")
        if current.transaction_count:
            raise CategoryRuleError(
                "categoria_com_transacoes", "Categoria com transações só pode ser arquivada."
            )
        if await conn.fetchval(queries.CATEGORY_HAS_HISTORY, category_id):
            raise CategoryRuleError(
                "categoria_com_historico", "Categoria com histórico só pode ser arquivada."
            )
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM fixed_costs WHERE category_id = $1::uuid)", category_id
        ):
            raise CategoryRuleError(
                "categoria_em_uso", "Categoria usada por um custo fixo só pode ser arquivada."
            )
        await conn.execute("DELETE FROM category_rules WHERE category_id = $1::uuid", category_id)
        await conn.execute("DELETE FROM categories WHERE id = $1::uuid", category_id)
    return True


# --------------------------------------------------------------------------------------------
# Ajustes › Regras e reaplicação (Story 2.10)
# --------------------------------------------------------------------------------------------


def _rule_row(r: asyncpg.Record) -> RuleRow:
    return RuleRow(
        id=str(r["id"]),
        pattern=r["pattern"],
        direction=r["direction"],
        category_id=str(r["category_id"]),
        category_label=r["category_label"],
        is_active=r["is_active"],
        origin=r["origin"],
        created_at=r["created_at"],
    )


async def list_rules(conn: asyncpg.Connection) -> list[RuleRow]:
    return [_rule_row(r) for r in await conn.fetch(queries.RULES_LIST)]


async def update_rule(conn: asyncpg.Connection, rule_id: str, body: RuleUpdate) -> RuleRow | None:
    pattern = body.pattern.strip().lower() if body.pattern is not None else None
    if pattern == "":
        raise ValueError("padrão vazio")
    if body.category_id is not None and not await queries.category_exists(conn, body.category_id):
        raise LookupError("categoria")
    try:
        found = await conn.fetchval(
            "UPDATE category_rules SET pattern = COALESCE($2, pattern), "
            "direction = COALESCE($3, direction), category_id = COALESCE($4::uuid, category_id), "
            "is_active = COALESCE($5, is_active) WHERE id = $1::uuid RETURNING id",
            rule_id,
            pattern,
            body.direction,
            body.category_id,
            body.is_active,
        )
    except asyncpg.UniqueViolationError:
        raise CategoryRuleError("regra_existente", "Já existe essa regra.") from None
    if found is None:
        return None
    return next(r for r in await list_rules(conn) if r.id == rule_id)


async def preview_rule(conn: asyncpg.Connection, body: RulePreviewIn) -> RulePreviewOut:
    rows = await conn.fetch(queries.RULE_MATCHES, body.pattern.strip(), body.direction)
    return RulePreviewOut(
        total=int(rows[0]["total"]) if rows else 0,
        items=[
            RuleMatch(
                id=str(r["id"]),
                date=r["date"],
                description=r["description"],
                amount=r["amount"],
                category_label=r["category_label"],
            )
            for r in rows
        ],
    )


class ReversedPeriodError(ValueError):
    """Fim do período antes do início."""


def _month_range(de: str, ate: str) -> tuple[date, date]:
    start = parse_periodo(de)
    last = parse_periodo(ate)
    if last < start:
        raise ReversedPeriodError("período")
    end = date(last.year + last.month // 12, last.month % 12 + 1, 1)
    return start, end


async def _reapply_plan(
    conn: asyncpg.Connection, de: str, ate: str
) -> tuple[ReapplyPreview, list[CategoryChange]]:
    start, end = _month_range(de, ate)
    rules = await load_rules(conn)
    labels = {str(r["id"]): r["label"] for r in await conn.fetch(queries.CATEGORY_LABELS)}
    changes: list[ReapplyChange] = []
    plan: list[CategoryChange] = []
    manual = 0
    port = month_status()
    closed_by_month: dict[date, bool] = {}
    for t in await conn.fetch(queries.TX_IN_RANGE, start, end):
        rule = best_rule(t["description"] or "", t["amount"], rules)
        if rule is None or rule.category_id == str(t["category_id"]):
            continue
        if t["category_source"] == "manual":
            manual += 1
            continue
        month = t["date"].replace(day=1)
        if month not in closed_by_month:
            closed_by_month[month] = await port.is_closed(conn, month)
        changes.append(
            ReapplyChange(
                transaction_id=str(t["id"]),
                date=t["date"],
                description=t["description"],
                amount=t["amount"],
                before=t["category_label"],
                after=labels.get(rule.category_id, rule.category_name),
                rule_pattern=rule.pattern,
            )
        )
        plan.append(CategoryChange(str(t["id"]), rule.category_id, "rule", rule.rule_id))
    closed_count = sum(1 for c in changes if closed_by_month[c.date.replace(day=1)])
    preview = ReapplyPreview(changes=changes, manual_unchanged=manual, closed_months=closed_count)
    return preview, plan


async def preview_reapply(conn: asyncpg.Connection, body: ReapplyIn) -> ReapplyPreview:
    preview, _ = await _reapply_plan(conn, body.de, body.ate)
    return preview


async def reapply_rules(conn: asyncpg.Connection, body: ReapplyIn) -> ReapplyResult:
    """Reaplica as regras ativas ao período: só não-manuais, via categorize() (cause reapply), numa
    transação; o mês tocado é marcado sujo pelo próprio categorize()."""
    async with conn.transaction():
        _, plan = await _reapply_plan(conn, body.de, body.ate)
        result = await categorize(conn, plan, cause="reapply")
    return ReapplyResult(changed=len(result.changed))


async def account_holders(conn: asyncpg.Connection) -> dict[str, str]:
    """Titular (pf/mei) de cada conta: a engine `ingest` agrupa o Bloco Fontes por ele."""
    rows = await conn.fetch("SELECT id::text AS id, holder FROM accounts WHERE holder IS NOT NULL")
    return {r["id"]: r["holder"] for r in rows}


# --------------------------------------------------------------------------------------------
# Revisão de transações (Story 3.10 — FR-9, FR-14)
# --------------------------------------------------------------------------------------------


class UncategorizedError(ValueError):
    """Confirmação com "Entrada/Saída a classificar"."""


def _origin(r: asyncpg.Record) -> Origin:
    if r["is_system"]:
        return "sem_sugestao"
    if r["category_source"] == "rule":
        return "regra"
    return "sugestao" if r["category_source"] == "suggestion" else "manual"


async def review_list(conn: asyncpg.Connection, batch_id: str | None) -> ReviewList:
    rows = await conn.fetch(queries.REVIEW_ITEMS, batch_id)
    items = [
        ReviewItem(
            id=str(r["id"]),
            date=r["date"],
            month=f"{r['date']:%Y-%m}",
            description=r["description"],
            amount=r["amount"],
            account_name=r["account_name"],
            category_id=str(r["category_id"]),
            category_label=r["category_label"],
            category_kind=r["category_kind"],
            origin=_origin(r),
            rule_pattern=r["rule_pattern"],
        )
        for r in rows
    ]
    months: dict[str, list[Decimal]] = {}
    for r in rows:
        months.setdefault(f"{r['date']:%Y-%m}", []).append(r["amount"])
    return ReviewList(
        items=items,
        months=[
            ReviewMonth(
                month=m,
                count=len(vals),
                entradas=sum((v for v in vals if v > 0), Decimal(0)),
                saidas=sum((v for v in vals if v < 0), Decimal(0)),
            )
            for m, vals in sorted(months.items())
        ],
        total=len(items),
    )


async def review_confirm(conn: asyncpg.Connection, body: ReviewConfirmIn) -> ReviewConfirmOut:
    """Marcadas → `confirmed` via categorize() (cause review). Categoria trocada vira `manual`;
    mantida, guarda a origem (regra/sugestão). "A classificar" não confirma."""
    chosen = list({c.category_id for c in body.items})
    if await conn.fetch(queries.SYSTEM_CATEGORIES, chosen):
        raise UncategorizedError("sem categoria")
    async with conn.transaction():
        state = {
            str(r["id"]): r
            for r in await conn.fetch(queries.REVIEW_STATE, [c.transaction_id for c in body.items])
        }
        changes: list[CategoryChange] = []
        for c in body.items:
            current = state.get(c.transaction_id)
            if current is None:
                raise LookupError(c.transaction_id)
            kept = str(current["category_id"]) == c.category_id
            source: Source = current["category_source"] if kept else "manual"
            rule = current["category_rule_id"] if kept and source == "rule" else None
            changes.append(
                CategoryChange(c.transaction_id, c.category_id, source, str(rule) if rule else None)
            )
        await categorize(
            conn, changes, cause="review", batch_id=body.lote, review_status="confirmed"
        )
        remaining = int(await conn.fetchval(queries.PENDING_COUNT, body.lote))
    return ReviewConfirmOut(confirmed=len(changes), remaining=remaining)


async def pending_review_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider: enquanto houver `pending`, "{n} transações a revisar." (ação Revisar)."""
    n = int(await conn.fetchval(queries.PENDING_COUNT, None))
    if n == 0:
        return []
    return [
        Alert(
            key="transacoes_a_revisar",
            fingerprint=fingerprint(n),
            severity="aviso",
            message="1 transação a revisar." if n == 1 else f"{n} transações a revisar.",
            action=AlertAction(
                label="Revisar", route="/caixa/transacoes", params={"revisar": "todas"}
            ),
            as_of=ctx.today,
        )
    ]


# --------------------------------------------------------------------------------------------
# Proposta de regra a partir da correção (Story 3.11 — FR-10)
# --------------------------------------------------------------------------------------------

_NO_DIGITS = re.compile(r"\d")


def propose_pattern(description: str) -> str:
    """Condição proposta: o trecho que nomeia o estabelecimento ou a pessoa (no memo do Nubank, o
    que vem depois do primeiro " - "), em minúscula e sem as partes com número."""
    parts = [p.strip() for p in description.split(" - ") if p.strip()]
    core = parts[1] if len(parts) > 1 else (parts[0] if parts else "")
    words = [w for w in core.lower().split() if not _NO_DIGITS.search(w)]
    return " ".join(words).strip(" -.,")


async def propose_rule(conn: asyncpg.Connection, body: RuleProposalIn) -> RuleProposal | None:
    tx = await conn.fetchrow(
        "SELECT description, amount FROM transactions WHERE id = $1::uuid", body.transaction_id
    )
    label = await conn.fetchval(queries.CATEGORY_LABEL_BY_ID, body.category_id)
    if tx is None or label is None:
        return None
    pattern = propose_pattern(tx["description"] or "")
    direction = "entrada" if tx["amount"] > 0 else "saida"
    affected = 0
    if pattern:
        proposed = Rule(
            pattern,
            direction,
            body.category_id,
            label,
            "",
            rule_id="proposta",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        rules = [*await load_rules(conn), proposed]
        affected = sum(
            1
            for t in await conn.fetch(
                queries.RULE_TARGETS, pattern, direction, body.category_id, body.transaction_id
            )
            if _wins(proposed.rule_id, t, rules)
        )
    return RuleProposal(
        pattern=pattern,
        direction=direction,
        category_id=body.category_id,
        category_label=label,
        affected=affected,
    )


def _wins(rule_id: str | None, tx: asyncpg.Record, rules: Sequence[Rule]) -> bool:
    best = best_rule(tx["description"] or "", tx["amount"], rules)
    return best is not None and best.rule_id == rule_id


async def create_rule(conn: asyncpg.Connection, body: RuleCreate) -> RuleCreated:
    """Grava a regra (origem `review` com `created_in_batch` quando vem da Revisão; `manual` fora
    dela) e a aplica às transações afetadas que não são manuais, por categorize() (cause
    rule_created)."""
    pattern = body.pattern.strip().lower()
    if not pattern:
        raise ValueError("padrão vazio")
    if not await queries.category_exists(conn, body.category_id):
        raise LookupError("categoria")
    async with conn.transaction():
        rule_id = str(
            await conn.fetchval(
                queries.UPSERT_RULE,
                pattern,
                body.direction,
                body.category_id,
                "review" if body.lote else "manual",
                body.lote,
            )
        )
        # Só onde a nova regra vence (AD-6: a mais longa; empate → a mais recente): uma regra curta
        # não passa por cima do que uma mais específica já categorizou.
        rules = await load_rules(conn)
        targets = [
            t
            for t in await conn.fetch(
                queries.RULE_TARGETS, pattern, body.direction, body.category_id, None
            )
            if _wins(rule_id, t, rules)
        ]
        result = await categorize(
            conn,
            [CategoryChange(str(t["id"]), body.category_id, "rule", rule_id) for t in targets],
            cause="rule_created",
            batch_id=body.lote,
        )
    row = next(r for r in await list_rules(conn) if r.id == rule_id)
    return RuleCreated(rule=row, applied=len(result.changed))


# --------------------------------------------------------------------------------------------
# Conferência encadeada da conta PF (Story 3.12 — FR-5)
# --------------------------------------------------------------------------------------------


@dataclass
class BalanceCheck:
    account_id: str
    intervals: list[BalanceInterval]

    @property
    def latest(self) -> BalanceInterval | None:
        return self.intervals[-1] if self.intervals else None


async def pf_balance_check(conn: asyncpg.Connection) -> BalanceCheck | None:
    """Intervalos entre os saldos informados da conta PF (`holder = pf`); a do MEI não confere."""
    account = await conn.fetchrow(queries.PF_ACCOUNT)
    if account is None:
        return None
    reported = [
        (r["as_of"], r["balance"])
        for r in await conn.fetch(queries.REPORTED_BALANCES, account["id"])
    ]
    movements = [
        (r["date"], r["amount"]) for r in await conn.fetch(queries.ACCOUNT_MOVEMENTS, account["id"])
    ]
    return BalanceCheck(str(account["id"]), chained_check(reported, movements))


# --------------------------------------------------------------------------------------------
# Conferência na tela e aviso de saldo divergente (Story 3.13 — FR-5, FR-14)
# --------------------------------------------------------------------------------------------


async def source_balances(conn: asyncpg.Connection) -> dict[str, dict[str, Any]]:
    """Bloco Fontes: conta PF "divergente" (o intervalo divergente mais recente) ou "conferido"
    (o intervalo mais recente). A conta MEI não confere."""
    check = await pf_balance_check(conn)
    if check is None or check.latest is None:
        return {}
    divergent = [i for i in check.intervals if not i.ok]
    if divergent:
        d = divergent[-1]
        return {"nubank_pf": {"status": "divergente", "as_of": d.end, "difference": d.difference}}
    return {
        "nubank_pf": {"status": "conferido", "as_of": check.latest.end, "difference": Decimal(0)}
    }


async def balance_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider: um aviso de divergência por intervalo da PF que não fecha ao centavo."""
    if "pf_balance_check" not in ctx.memo:
        ctx.memo["pf_balance_check"] = await pf_balance_check(conn)
    check: BalanceCheck | None = ctx.memo["pf_balance_check"]
    if check is None:
        return []
    return [
        Alert(
            key=f"saldo_divergente:pf:{i.end.isoformat()}",
            fingerprint=fingerprint(i.start, i.end, i.difference),
            severity="divergencia",
            message=f"Saldo divergente em {brl(abs(i.difference))} na conta PF.",
            action=AlertAction(
                label="Ver transações",
                route="/caixa/transacoes",
                params={
                    "periodo": f"{i.end:%Y-%m}",
                    "conferencia": f"{i.start.isoformat()}_{i.end.isoformat()}",
                },
            ),
            as_of=i.end,
        )
        for i in check.intervals
        if not i.ok
    ]


async def balance_candidates(
    conn: asyncpg.Connection, start: date, end: date
) -> BalanceCandidates | None:
    """Transações do intervalo, das que têm valor mais perto da diferença para as mais longe."""
    check = await pf_balance_check(conn)
    if check is None:
        return None
    interval = next((i for i in check.intervals if (i.start, i.end) == (start, end)), None)
    if interval is None:
        return None
    rows = await conn.fetch(queries.INTERVAL_TRANSACTIONS, uuid.UUID(check.account_id), start, end)
    target = abs(interval.difference)
    ordered = sorted(rows, key=lambda r: (abs(abs(r["amount"]) - target), r["date"]))
    return BalanceCandidates(
        start=start,
        end=end,
        difference=interval.difference,
        items=[
            BalanceCandidate(
                id=str(r["id"]),
                date=r["date"],
                description=r["description"],
                amount=r["amount"],
                category_label=r["category_label"],
            )
            for r in ordered
        ],
    )


# --------------------------------------------------------------------------------------------
# Desfazer lote: transações de fora que perderam a regra e a âncora do saldo (Story 3.14)
# --------------------------------------------------------------------------------------------


async def recategorize_without_rules(
    conn: asyncpg.Connection, rows: Sequence[asyncpg.Record], batch_id: str
) -> None:
    """Transações de fora do lote desfeito categorizadas por uma regra que saiu: voltam por
    categorize() sem ela — outra regra que case, senão a sugestão, senão "a classificar" — sempre
    pendentes."""
    if not rows:
        return
    from .importer import suggestion_history  # import tardio: o importer depende deste módulo
    from .suggest import best_suggestion

    rules = await load_rules(conn)
    history = await suggestion_history(conn)
    pending = {
        True: await queries.category_id_by_key(conn, "sistema:entrada_a_classificar"),
        False: await queries.category_id_by_key(conn, "sistema:saida_a_classificar"),
    }
    changes: list[CategoryChange] = []
    for r in rows:
        rule = best_rule(r["description"] or "", r["amount"], rules)
        if rule is not None:
            changes.append(CategoryChange(str(r["id"]), rule.category_id, "rule", rule.rule_id))
            continue
        hint = best_suggestion(r["description"] or "", r["amount"], history)
        target = hint.category_id if hint else pending[r["amount"] > 0]
        changes.append(CategoryChange(str(r["id"]), target, "suggestion"))
    await categorize(conn, changes, cause="undo", batch_id=batch_id, review_status="pending")


async def recompute_anchor(conn: asyncpg.Connection, account_id: Any) -> None:
    """Âncora = o saldo informado mais antigo que sobrou; sem nenhum, a conta fica sem âncora."""
    first = await conn.fetchrow(
        "SELECT as_of, balance FROM account_balances WHERE account_id = $1 ORDER BY as_of LIMIT 1",
        account_id,
    )
    if first is None:
        await conn.execute(
            "UPDATE accounts SET opening_balance = NULL, opening_balance_date = NULL WHERE id = $1",
            account_id,
        )
        return
    moves = [
        (r["date"], r["amount"]) for r in await conn.fetch(queries.ACCOUNT_MOVEMENTS, account_id)
    ]
    await conn.execute(
        "UPDATE accounts SET opening_balance = $2, opening_balance_date = $3 WHERE id = $1",
        account_id,
        opening_balance(first["balance"], first["as_of"], moves),
        first["as_of"],
    )


# --------------------------------------------------------------------------------------------
# Termos do Painel (Story 4.1 — AD-7): resultado do mês e saldo das contas
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DatedAmount:
    value: Decimal
    as_of: date | None


async def month_result_for(conn: asyncpg.Connection, month: date) -> DatedAmount | None:
    """Resultado do mês por `ledger/calc.month_result`; `as_of` = dados até (último lançamento
    do mês, ou o fim do mês). Mês sem transação → None."""
    rows = await queries.month_movements(conn, [month])
    if not rows:
        return None
    value = month_result([Movement(r["amount"], r["kind"], r["role"]) for r in rows])
    last = await conn.fetchval(queries.LAST_DATE_IN_MONTH, month)
    return DatedAmount(value, last)


async def accounts_balance(conn: asyncpg.Connection, until: date) -> DatedAmount:
    """Saldo calculado das contas com âncora (`opening_balance`) até a data; a conta do MEI fica
    sempre zerada e não tem âncora."""
    total = Decimal(0)
    latest: date | None = None
    for acc in await conn.fetch(queries.ANCHORED_ACCOUNTS):
        moves = [
            (r["date"], r["amount"])
            for r in await conn.fetch(queries.ACCOUNT_MOVEMENTS, acc["id"])
        ]
        total += computed_balance(acc["opening_balance"], moves, until)
        dated = [d for d, _ in moves if d <= until]
        if dated:
            latest = max(latest or dated[-1], dated[-1])
    return DatedAmount(total, latest)


async def pending_review_count(conn: asyncpg.Connection) -> int:
    return int(await conn.fetchval(queries.PENDING_COUNT, None))
