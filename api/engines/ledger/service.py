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
from datetime import date, timedelta
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
from engines.common.dates import add_months, month_end, month_label, parse_periodo, today_brt
from engines.common.month_status import month_status

from . import queries
from .calc import (
    MATCH_DAYS_AFTER,
    MATCH_DAYS_BEFORE,
    BalanceInterval,
    Consumed,
    CostDue,
    CostMatch,
    Decision,
    Movement,
    Rule,
    SpendTx,
    TxCandidate,
    best_rule,
    chained_check,
    computed_balance,
    consumido,
    devolucoes,
    due_date,
    gastos,
    investido,
    match_fixed_costs,
    month_checked,
    month_result,
    opening_balance,
    resgates,
    savings_rate,
    work_income,
)
from .calc import receitas as calc_receitas
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
    FixedCostDecisionIn,
    FixedCostIn,
    FixedCostMonth,
    FixedCostMonthItem,
    FixedCostPatch,
    FixedCostRow,
    FixedCostTx,
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
    """Provider (Story 6.3): custo fixo sem pagamento casado — "{Custo} vence em {dd/mm/aaaa}."
    faltando 3 dias ou menos; vencido, "{Custo} atrasado desde {dd/mm/aaaa}.". Mês atual, o
    seguinte (vencimento no começo dele) e o anterior, se ainda aberto."""
    current = ctx.today.replace(day=1)
    months = [current, add_months(current, 1)]  # o seguinte: vencimento nos primeiros dias
    previous = add_months(current, -1)
    if not await ctx.months.is_closed(conn, previous):
        months.insert(0, previous)
    alerts: list[Alert] = []
    for month in months:
        view = await fixed_cost_month(conn, month, today=ctx.today)
        for item in view.items:
            if item.status == "atrasado":
                message = f"{item.name} atrasado desde {item.due_date:%d/%m/%Y}."
            elif item.status == "vencendo":
                message = f"{item.name} vence em {item.due_date:%d/%m/%Y}."
            else:
                continue
            alerts.append(
                Alert(
                    key=f"custo_fixo:{item.id}:{month:%Y-%m}",
                    fingerprint=fingerprint(item.status, item.due_date),
                    severity="aviso",
                    message=message,
                    action=AlertAction(
                        label="Ver custos fixos",
                        route="/caixa/custos-fixos",
                        params={"periodo": f"{month:%Y-%m}"},
                    ),
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
    end = add_months(month, 1)
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


async def review_list(
    conn: asyncpg.Connection, batch_id: str | None, month: date | None = None
) -> ReviewList:
    """Pendentes do lote (ou todas), opcionalmente só de um mês (Assistente de recuperação)."""
    rows = await conn.fetch(queries.REVIEW_ITEMS, batch_id, month)
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
            (r["date"], r["amount"]) for r in await conn.fetch(queries.ACCOUNT_MOVEMENTS, acc["id"])
        ]
        total += computed_balance(acc["opening_balance"], moves, until)
        dated = [d for d, _ in moves if d <= until]
        if dated:
            latest = max(latest or dated[-1], dated[-1])
    return DatedAmount(total, latest)


async def pending_review_count(conn: asyncpg.Connection) -> int:
    return int(await conn.fetchval(queries.PENDING_COUNT, None))


async def pending_in_month(conn: asyncpg.Connection, month: date) -> int:
    """Transações `pending` do mês (passo Revisar do Assistente de recuperação)."""
    end = add_months(month, 1)
    return int(
        await conn.fetchval(
            "SELECT count(*) FROM transactions WHERE review_status = 'pending' "
            "AND date >= $1 AND date < $2",
            month,
            end,
        )
    )


# --------------------------------------------------------------------------------------------
# Construtores do mês para o resumo (Story 5.2 — AD-8): termos da AD-7 e as quebras
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerMonth:
    month: date
    receitas: Decimal
    trabalho: Decimal
    resgates: Decimal
    devolucoes: Decimal
    gastos: Decimal
    investido: Decimal
    taxa_poupanca: Decimal | None  # fração
    resultado: Decimal
    receitas_por_pagador: dict[str, Decimal]
    gastos_por_categoria: dict[str, Decimal]
    data_as_of: date | None  # último lançamento do mês
    has_data: bool


async def ledger_month(conn: asyncpg.Connection, month: date) -> LedgerMonth:
    rows = await queries.month_movements(conn, [month])
    moves = [Movement(r["amount"], r["kind"], r["role"]) for r in rows]
    return LedgerMonth(
        month=month,
        receitas=calc_receitas(moves),
        trabalho=work_income(moves),
        resgates=resgates(moves),
        devolucoes=devolucoes(moves),
        gastos=gastos(moves),
        investido=investido(moves),
        taxa_poupanca=savings_rate(moves),
        resultado=month_result(moves),
        receitas_por_pagador={
            r["payer"]: r["total"] for r in await conn.fetch(queries.INCOME_BY_PAYER, month)
        },
        gastos_por_categoria={
            r["category_id"]: r["total"]
            for r in await conn.fetch(queries.EXPENSES_BY_CATEGORY, month)
        },
        data_as_of=await conn.fetchval(queries.LAST_DATE_IN_MONTH, month),
        has_data=bool(rows),
    )


async def pf_month_checked(conn: asyncpg.Connection, month_end: date) -> bool | None:
    """Saldo PF conferido no fim do mês (AD-7); sem saldo informado → None."""
    check = await pf_balance_check(conn)
    if check is None or not check.intervals:
        return None
    return month_checked(check.intervals, month_end)


# --------------------------------------------------------------------------------------------
# Precondições do fechamento que o ledger registra em `closing` (Story 5.3 — AD-8)
# --------------------------------------------------------------------------------------------


async def close_checks(conn: asyncpg.Connection, month: date) -> list[dict[str, Any]]:
    """Pendentes e saldo PF divergente bloqueiam; PF sem saldo conferido e MEI que não cobre o
    mês pedem "fechar mesmo assim"."""
    from engines.ingest import service as ingest_service

    found: list[dict[str, Any]] = []
    end = month_end(month)
    pending = await pending_in_month(conn, month)
    label = month_label(month)
    if pending:
        found.append(
            {
                "code": "transacoes_pendentes",
                "kind": "bloqueia",
                "message": f"{pending} transações a revisar em {label}.",
            }
        )
    check = await pf_balance_check(conn)
    intervals = check.intervals if check is not None else []
    for i in intervals:
        if not i.ok and i.start < end and i.end >= month:
            found.append(
                {
                    "code": "saldo_pf_divergente",
                    "kind": "bloqueia",
                    "message": f"Saldo da conta PF divergente em {brl(abs(i.difference))} "
                    f"({i.start:%d/%m/%Y} a {i.end:%d/%m/%Y}).",
                    "amount": abs(i.difference),
                }
            )
    if not any(f["code"] == "saldo_pf_divergente" for f in found) and not month_checked(
        intervals, end
    ):
        found.append(
            {
                "code": "saldo_pf_nao_conferido",
                "kind": "confirma",
                "message": f"Saldo da conta PF não conferido no fim de {label}.",
            }
        )
    sources = await ingest_service.sources(conn, today_brt(), with_balances=False)
    mei = next((s for s in sources if s.key == "nubank_mei"), None)
    if mei is not None and (mei.updated_until is None or mei.updated_until < end):
        found.append(
            {"code": "mei_nao_cobre", "kind": "confirma", "message": f"MEI não cobre {label}."}
        )
    return found


# --------------------------------------------------------------------------------------------
# Custos fixos com vigência e casamento (Story 6.1 — FR-18, AD-9)
# --------------------------------------------------------------------------------------------

_FIXED_COST_ROW = """
    SELECT f.id, f.name, f.amount, f.due_day, f.category_id, f.valid_from, f.valid_to,
           CASE WHEN c.id IS NULL THEN f.category WHEN g.is_system THEN c.name
                ELSE g.name || ' › ' || c.name END AS category_label
    FROM fixed_costs f LEFT JOIN categories c ON c.id = f.category_id
    LEFT JOIN category_groups g ON g.id = c.group_id
"""


class FixedCostNotFound(LookupError):
    pass


class UnknownCategoryError(LookupError):
    pass


def _fixed_cost_row(r: asyncpg.Record) -> FixedCostRow:
    return FixedCostRow(
        id=str(r["id"]),
        name=r["name"],
        amount=r["amount"],
        due_day=r["due_day"],
        category_id=str(r["category_id"]) if r["category_id"] else None,
        category_label=r["category_label"],
        valid_from=r["valid_from"],
        valid_to=r["valid_to"],
    )


async def list_fixed_costs_v2(conn: asyncpg.Connection) -> list[FixedCostRow]:
    """Cadastro (Ajustes › Custos fixos): os vigentes hoje ou no futuro, por vencimento."""
    current = today_brt().replace(day=1)
    rows = await conn.fetch(
        _FIXED_COST_ROW
        + " WHERE f.valid_to IS NULL OR f.valid_to >= $1 ORDER BY f.due_day, f.name",
        current,
    )
    return [_fixed_cost_row(r) for r in rows]


async def _fixed_cost(conn: asyncpg.Connection, cost_id: str) -> FixedCostRow:
    row = await conn.fetchrow(_FIXED_COST_ROW + " WHERE f.id = $1::uuid", cost_id)
    if row is None:
        raise FixedCostNotFound(cost_id)
    return _fixed_cost_row(row)


async def create_fixed_cost(conn: asyncpg.Connection, body: FixedCostIn) -> FixedCostRow:
    label = await conn.fetchval(
        "SELECT name FROM categories WHERE id = $1::uuid", str(body.category_id)
    )
    if label is None:
        raise UnknownCategoryError(str(body.category_id))
    cost_id = await conn.fetchval(
        "INSERT INTO fixed_costs (name, amount, due_day, category, category_id, valid_from) "
        "VALUES ($1, $2, $3, $4, $5::uuid, $6) RETURNING id",
        body.name,
        body.amount,
        body.due_day,
        label,
        str(body.category_id),
        (body.valid_from or today_brt()).replace(day=1),
    )
    return await _fixed_cost(conn, str(cost_id))


async def update_fixed_cost(
    conn: asyncpg.Connection, cost_id: str, body: FixedCostPatch
) -> FixedCostRow:
    await _fixed_cost(conn, cost_id)
    label = None
    if body.category_id is not None:
        label = await conn.fetchval(
            "SELECT name FROM categories WHERE id = $1::uuid", str(body.category_id)
        )
        if label is None:
            raise UnknownCategoryError(str(body.category_id))
    await conn.execute(
        "UPDATE fixed_costs SET name = COALESCE($2, name), amount = COALESCE($3, amount), "
        "due_day = COALESCE($4, due_day), category_id = COALESCE($5::uuid, category_id), "
        "category = COALESCE($6, category) WHERE id = $1::uuid",
        cost_id,
        body.name,
        body.amount,
        body.due_day,
        str(body.category_id) if body.category_id is not None else None,
        label,
    )
    return await _fixed_cost(conn, cost_id)


async def delete_fixed_cost(conn: asyncpg.Connection, cost_id: str) -> None:
    """Excluir encerra a vigência no mês anterior: some do mês atual em diante e os meses passados
    (casados na leitura, sem linha gravada) continuam com ele. Custo que só vale a partir deste mês
    não tem passado: apaga."""
    cost = await _fixed_cost(conn, cost_id)
    current = today_brt().replace(day=1)
    if cost.valid_from >= current:
        await conn.execute("DELETE FROM fixed_costs WHERE id = $1::uuid", cost_id)
    else:
        await conn.execute(
            "UPDATE fixed_costs SET valid_to = $2, is_active = false WHERE id = $1::uuid",
            cost_id,
            add_months(current, -1),
        )


async def fixed_costs_due(conn: asyncpg.Connection, month: date) -> list[asyncpg.Record]:
    """Custos vigentes no mês (valid_from ≤ mês ≤ valid_to)."""
    return list(
        await conn.fetch(
            _FIXED_COST_ROW
            + " WHERE f.valid_from <= $1 AND (f.valid_to IS NULL OR f.valid_to >= $1)"
            " ORDER BY f.due_day, f.name",
            month,
        )
    )


async def fixed_cost_matches(conn: asyncpg.Connection, month: date) -> list[CostMatch]:
    """Casamento do mês (AD-9, derivado na leitura): decisões de `fixed_cost_payments` e o guloso
    de `ledger/calc` sobre as saídas do próprio mês (a janela −5/+5 do vencimento não cruza o mês:
    a mesma transação nunca paga custo de outro mês nem conta duas vezes). A transação escolhida
    numa decisão entra mesmo fora da janela."""
    costs = [
        CostDue(str(r["id"]), r["amount"], due_date(month, r["due_day"]))
        for r in await fixed_costs_due(conn, month)
    ]
    if not costs:
        return []
    start = max(min(c.due for c in costs) - timedelta(days=MATCH_DAYS_BEFORE), month)
    end = min(max(c.due for c in costs) + timedelta(days=MATCH_DAYS_AFTER), month_end(month))
    decided = await conn.fetch(
        "SELECT fixed_cost_id, kind, transaction_id FROM fixed_cost_payments WHERE month = $1",
        month,
    )
    txs = [
        TxCandidate(str(r["id"]), -r["amount"], r["date"])
        for r in await conn.fetch(
            "SELECT id, amount, date FROM transactions WHERE amount < 0 AND ((kind = 'expense' "
            "AND date BETWEEN $1 AND $2) OR id = ANY($3::uuid[]))",
            start,
            end,
            [r["transaction_id"] for r in decided if r["transaction_id"]],
        )
    ]
    decisions = [
        Decision(
            str(r["fixed_cost_id"]),
            r["kind"],
            str(r["transaction_id"]) if r["transaction_id"] else None,
        )
        for r in decided
    ]
    found = match_fixed_costs(costs, txs, decisions)
    return [found[c.cost_id] for c in costs]


# --------------------------------------------------------------------------------------------
# Caixa › Custos fixos: o mês com casamento e as decisões (Story 6.2 — FR-18, AD-9)
# --------------------------------------------------------------------------------------------

DUE_SOON_DAYS = 3  # "vencendo": faltam 3 dias ou menos
_STATUS_ORDER = {"atrasado": 0, "vencendo": 1, "pendente": 2, "manual": 3, "pago": 4}


class MonthClosedError(Exception):
    """Mês fechado: `fixed_cost_payments` é só leitura até reabrir (AD-8)."""


class DecisionError(ValueError):
    pass


class TransactionInUseError(Exception):
    """A transação já paga outro custo fixo (decisão confirmada)."""


def _cost_status(match: CostMatch, due: date, today: date) -> str:
    if match.status in ("pago", "manual"):
        return match.status
    if due < today:
        return "atrasado"
    return "vencendo" if (due - today).days <= DUE_SOON_DAYS else "pendente"


async def fixed_cost_month(
    conn: asyncpg.Connection, month: date, *, today: date | None = None
) -> FixedCostMonth:
    """A lista do mês (ordem atrasado → pago) com a transação casada, as candidatas e os totais."""
    today = today or today_brt()
    costs = {str(r["id"]): r for r in await fixed_costs_due(conn, month)}
    matches = await fixed_cost_matches(conn, month)
    tx_ids = {m.transaction_id for m in matches if m.transaction_id} | {
        t for m in matches for t in m.candidates
    }
    txs = {
        str(r["id"]): FixedCostTx(
            id=str(r["id"]), date=r["date"], description=r["description"], amount=r["amount"]
        )
        for r in await conn.fetch(
            "SELECT id, date, description, amount FROM transactions WHERE id = ANY($1::uuid[])",
            list(tx_ids),
        )
    }
    items: list[FixedCostMonthItem] = []
    for m in matches:
        row = costs[m.cost_id]
        due = due_date(month, row["due_day"])
        items.append(
            FixedCostMonthItem(
                id=m.cost_id,
                name=row["name"],
                amount=row["amount"],
                due_date=due,
                category_label=row["category_label"],
                status=_cost_status(m, due, today),
                source=m.source,
                transaction=txs.get(m.transaction_id) if m.transaction_id else None,
                candidates=[txs[t] for t in m.candidates if t in txs],
            )
        )
    items.sort(key=lambda i: (_STATUS_ORDER[i.status], i.due_date, i.name))
    paid = [i for i in items if i.status in ("pago", "manual")]
    paid_total = sum(
        (-i.transaction.amount if i.transaction else i.amount for i in paid), Decimal(0)
    )
    total = sum((i.amount for i in items), Decimal(0))
    return FixedCostMonth(
        month=month,
        closed=await month_status().is_closed(conn, month),
        items=items,
        count=len(items),
        paid_count=len(paid),
        total=total,
        paid_total=paid_total,
        pending_total=sum((i.amount for i in items if i not in paid), Decimal(0)),
        as_of=await conn.fetchval(
            "SELECT max(date) FROM transactions WHERE date <= $1", month_end(month)
        ),
    )


async def decide_fixed_cost(
    conn: asyncpg.Connection, cost_id: str, body: FixedCostDecisionIn
) -> None:
    """Grava a decisão do mês (uma por custo e mês; a nova substitui a anterior)."""
    month = parse_periodo(body.mes)
    await _fixed_cost(conn, cost_id)
    if await month_status().is_closed(conn, month):
        raise MonthClosedError(body.mes)
    if (body.kind == "manual") != (body.transaction_id is None):
        raise DecisionError("transação obrigatória, exceto em manual")
    if body.transaction_id is not None:
        tx = await conn.fetchrow(
            "SELECT date, amount FROM transactions WHERE id = $1::uuid", str(body.transaction_id)
        )
        if tx is None or tx["amount"] >= 0 or tx["date"].replace(day=1) != month:
            raise DecisionError("a transação precisa ser uma saída do mês")
        if body.kind in ("confirmado", "corrigido"):
            other = await conn.fetchval(
                "SELECT f.name FROM fixed_cost_payments p JOIN fixed_costs f "
                "ON f.id = p.fixed_cost_id WHERE p.transaction_id = $1::uuid "
                "AND p.kind IN ('confirmado', 'corrigido') AND p.fixed_cost_id <> $2::uuid",
                str(body.transaction_id),
                cost_id,
            )
            if other is not None:
                raise TransactionInUseError(other)
    await conn.execute(
        "INSERT INTO fixed_cost_payments (fixed_cost_id, month, kind, transaction_id) "
        "VALUES ($1::uuid, $2, $3, $4::uuid) ON CONFLICT (fixed_cost_id, month) DO UPDATE "
        "SET kind = EXCLUDED.kind, transaction_id = EXCLUDED.transaction_id, created_at = now()",
        cost_id,
        month,
        body.kind,
        str(body.transaction_id) if body.transaction_id else None,
    )


async def clear_fixed_cost_decision(conn: asyncpg.Connection, cost_id: str, mes: str) -> None:
    """Desfaz a decisão do mês: o custo volta ao casamento automático."""
    month = parse_periodo(mes)
    if await month_status().is_closed(conn, month):
        raise MonthClosedError(mes)
    await conn.execute(
        "DELETE FROM fixed_cost_payments WHERE fixed_cost_id = $1::uuid AND month = $2",
        cost_id,
        month,
    )


# --------------------------------------------------------------------------------------------
# Fatos do mês para o orçamento (Story 6.5 — AD-7): o que `planning/calc` precisa do caixa
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BudgetFacts:
    trabalho: Decimal
    por_pagador: dict[str, Decimal]
    resgates: Decimal
    resgates_itens: list[tuple[date, str, Decimal]]  # (data, descrição, valor)
    gastos: Decimal
    investido: Decimal
    consumed: Consumed
    fixed: list[tuple[Decimal, Decimal | None]]  # (cadastrado, pago ou None)
    fixed_paid: Decimal
    fixed_pending: Decimal
    # consumido por grupo → subcategoria: (grupo, subcategoria) → (valor, nº de transações)
    by_category: dict[tuple[str, str], tuple[Decimal, int]]
    as_of: date | None
    taxa_poupanca: Decimal | None  # fração


async def budget_facts(conn: asyncpg.Connection, month: date) -> BudgetFacts:
    """Transações do mês por papel, o casamento dos custos fixos e o consumido em baldes."""
    rows = await conn.fetch(
        "SELECT t.id, t.date, t.amount, t.kind, c.role, t.payer, t.description, "
        "g.name AS group_name, c.name AS category_name "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "JOIN category_groups g ON g.id = c.group_id "
        "WHERE t.date >= $1 AND t.date < $2 ORDER BY t.date",
        month,
        add_months(month, 1),
    )
    moves = [Movement(r["amount"], r["kind"], r["role"]) for r in rows]
    matches = await fixed_cost_matches(conn, month)
    costs = {str(r["id"]): r["amount"] for r in await fixed_costs_due(conn, month)}
    paid_amounts = {
        str(r["id"]): -r["amount"]
        for r in await conn.fetch(
            "SELECT id, amount FROM transactions WHERE id = ANY($1::uuid[])",
            [m.transaction_id for m in matches if m.transaction_id],
        )
    }
    fixed: list[tuple[Decimal, Decimal | None]] = []
    for m in matches:
        if m.status == "manual":
            fixed.append((costs[m.cost_id], costs[m.cost_id]))
        elif m.status == "pago" and m.transaction_id:
            fixed.append((costs[m.cost_id], paid_amounts.get(m.transaction_id)))
        else:
            fixed.append((costs[m.cost_id], None))
    matched = {m.transaction_id for m in matches if m.transaction_id}
    spend = [SpendTx(str(r["id"]), r["amount"], r["kind"], r["role"]) for r in rows]
    by_category: dict[tuple[str, str], tuple[Decimal, int]] = {}
    for r in rows:
        if r["kind"] != "expense" or str(r["id"]) in matched or r["role"] == "divida":
            continue
        key = (r["group_name"], r["category_name"])
        value, n = by_category.get(key, (Decimal(0), 0))
        by_category[key] = (value - r["amount"], n + 1)
    por_pagador: dict[str, Decimal] = {}
    for r in rows:
        if r["role"] == "work_income":
            payer = r["payer"] or "Sem pagador"
            por_pagador[payer] = por_pagador.get(payer, Decimal(0)) + r["amount"]
    return BudgetFacts(
        trabalho=work_income(moves),
        por_pagador=por_pagador,
        resgates=resgates(moves),
        resgates_itens=[
            (r["date"], r["description"] or "", r["amount"]) for r in rows if r["role"] == "resgate"
        ],
        gastos=gastos(moves),
        investido=investido(moves),
        consumed=consumido(spend, {t for t in matched if t is not None}),
        fixed=fixed,
        fixed_paid=sum((p for _, p in fixed if p is not None), Decimal(0)),
        fixed_pending=sum((c for c, p in fixed if p is None), Decimal(0)),
        by_category=by_category,
        as_of=max((r["date"] for r in rows), default=None),
        taxa_poupanca=savings_rate(moves),
    )
