"""Engine `planning` (camada 4): plano do mês (`month_plans`) e o orçamento pelos termos de
`planning/calc` sobre os fatos de `ledger` (AD-7). Num mês fechado o plano é só leitura (AD-8)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.models import Valued
from engines.common.month_status import month_status
from engines.ledger import expected_incomes
from engines.ledger import service as ledger_service

from . import calc, goals
from .models import (
    ConsumedGroup,
    ConsumedSub,
    MonthBudget,
    MonthPlanOut,
    PayerAmount,
    ResgateItem,
)

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


class MonthClosedError(Exception):
    """Mês fechado: o plano é só leitura até reabrir."""


async def month_plan(conn: asyncpg.Connection, month: date) -> MonthPlanOut:
    row = await conn.fetchrow(
        "SELECT dividas, aporte_planejado FROM month_plans WHERE month = $1", month
    )
    return MonthPlanOut(
        month=month,
        dividas=row["dividas"] if row else None,
        aporte_planejado=row["aporte_planejado"] if row else None,
    )


async def set_dividas(conn: asyncpg.Connection, month: date, value: Decimal | None) -> MonthPlanOut:
    """Grava as dívidas do mês (None = volta ao pré-preenchido). Recusa em mês fechado."""
    if await month_status().is_closed(conn, month):
        raise MonthClosedError(f"{month:%Y-%m}")
    await conn.execute(
        "INSERT INTO month_plans (month, dividas) VALUES ($1, $2) ON CONFLICT (month) DO UPDATE "
        "SET dividas = EXCLUDED.dividas, updated_at = now()",
        month,
        value,
    )
    return await month_plan(conn, month)


async def set_aporte(conn: asyncpg.Connection, month: date, value: Decimal | None) -> MonthPlanOut:
    """Story 8.4: grava o aporte planejado do mês (None = não definido). Recusa em mês fechado."""
    if await month_status().is_closed(conn, month):
        raise MonthClosedError(f"{month:%Y-%m}")
    await conn.execute(
        "INSERT INTO month_plans (month, aporte_planejado) VALUES ($1, $2) ON CONFLICT (month) "
        "DO UPDATE SET aporte_planejado = EXCLUDED.aporte_planejado, updated_at = now()",
        month,
        value,
    )
    return await month_plan(conn, month)


LOCK_PREFIXES = ("goal:", "class:", "asset:")


class InvalidLockKey(ValueError):
    pass


async def set_lock(conn: asyncpg.Connection, month: date, key: str, value: Decimal | None) -> None:
    """Story 8.6: trava (ou destrava, com None) uma linha da distribuição do mês — `goal:<id>`,
    `class:<classe>` ou `asset:<id>` — em `month_plans.travas`. Recusa em mês fechado."""
    if not key.startswith(LOCK_PREFIXES) or key.split(":", 1)[1] == "":
        raise InvalidLockKey(key)
    if await month_status().is_closed(conn, month):
        raise MonthClosedError(f"{month:%Y-%m}")
    if value is None:
        await conn.execute(
            "UPDATE month_plans SET travas = travas - $2, updated_at = now() WHERE month = $1",
            month,
            key,
        )
        return
    await conn.execute(
        "INSERT INTO month_plans (month, travas) "
        "VALUES ($1, jsonb_build_object($2::text, $3::text)) "
        "ON CONFLICT (month) DO UPDATE SET travas = month_plans.travas || "
        "jsonb_build_object($2::text, $3::text), updated_at = now()",
        month,
        key,
        str(value),
    )


async def ensure_month_plan(conn: asyncpg.Connection, month: date, *, mode: str) -> MonthPlanOut:
    """Plano do mês para o fechamento (Story 6.8). `retro`: dívidas = Σ das transações de role
    `divida` não casadas a custo fixo; aporte planejado nulo (`nao_definido`) — só quando o mês
    ainda não tem plano. Caminho de serviço do `refechar`/`close_retro` (sem a trava de mês
    fechado)."""
    if mode != "retro":
        raise ValueError(mode)
    facts = await ledger_service.budget_facts(conn, month)
    # só cria: o que o Vitor já informou no mês (dívidas, aporte) nunca é sobrescrito
    await conn.execute(
        "INSERT INTO month_plans (month, dividas, aporte_planejado) VALUES ($1, $2, NULL) "
        "ON CONFLICT (month) DO NOTHING",
        month,
        facts.consumed.dividas,
    )
    return await month_plan(conn, month)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    return (part / whole * _HUNDRED).quantize(_CENT) if whole else Decimal(0)


def _groups(facts: ledger_service.BudgetFacts, total: Decimal) -> list[ConsumedGroup]:
    """Todos os grupos de gasto (o grupo só de custo fixo também aparece),
    do maior consumido para o menor; os fixos e as dívidas de cada grupo ao lado."""
    groups: dict[str, list[tuple[str, Decimal, int]]] = {
        g: [] for g in (*facts.expense_groups, *facts.fixed_by_group, *facts.debt_by_group)
    }
    for (group, sub), (value, n) in facts.by_category.items():
        groups.setdefault(group, []).append((sub, value, n))
    out = [
        ConsumedGroup(
            group=g,
            value=sum((v for _, v, _ in subs), Decimal(0)),
            pct=_pct(sum((v for _, v, _ in subs), Decimal(0)), total),
            count=sum(n for *_, n in subs),
            subcategories=[
                ConsumedSub(name=s, value=v, pct=_pct(v, total), count=n)
                for s, v, n in sorted(subs, key=lambda x: -x[1])
            ],
            fixos=facts.fixed_by_group.get(g, Decimal(0)),
            dividas=facts.debt_by_group.get(g, Decimal(0)),
        )
        for g, subs in groups.items()
    ]
    return sorted(out, key=lambda g: (-g.value, -g.fixos, g.group))


async def month_budget(conn: asyncpg.Connection, month: date) -> MonthBudget:
    """O orçamento do mês ao vivo: fatos do caixa + plano do mês → termos de `planning/calc`."""
    facts = await ledger_service.budget_facts(conn, month)
    plan = await month_plan(conn, month)
    b = calc.budget(
        calc.BudgetInput(
            trabalho=facts.trabalho,
            resgates=facts.resgates,
            custos_fixos=calc.custos_fixos_do_mes(facts.fixed),
            aporte_planejado=plan.aporte_planejado,
            dividas_informadas=plan.dividas,
            dividas_prefill=facts.consumed.dividas,
            consumido=facts.consumed.total,
        )
    )
    as_of = facts.as_of
    # Story 8.1: resgate de ativo vinculado a objetivo financia primeiro (por objetivo)
    linked = await goals.linked_assets(conn)
    goal_names = {str(r["id"]): r["name"] for r in await conn.fetch("SELECT id, name FROM goals")}
    por_objetivo, por_carteira = calc.financiado_split(
        b.consumo_financiado,
        sum((x for _, _, x, asset in facts.resgates_itens if asset in linked), Decimal(0)),
    )

    def v(value: Decimal) -> Valued[Decimal]:
        return Valued[Decimal](value=value, as_of=as_of, source="ledger")

    planned = await expected_incomes.month_incomes(conn, month)
    planned_total, a_receber = expected_incomes.planned_totals(planned)
    rate = facts.taxa_poupanca
    groups_total = sum((v for v, _ in facts.by_category.values()), Decimal(0))
    return MonthBudget(
        month=month,
        as_of=as_of,
        source="live",
        closed=await month_status().is_closed(conn, month),
        trabalho=v(b.trabalho),
        trabalho_por_pagador=[
            PayerAmount(payer=p, value=x)
            for p, x in sorted(facts.por_pagador.items(), key=lambda i: -i[1])
        ],
        resgates=v(b.resgates_considerados),
        resgates_itens=[
            ResgateItem(
                date=d,
                description=desc,
                value=x,
                goal=goal_names.get(linked[asset]) if asset in linked else None,
            )
            for d, desc, x, asset in facts.resgates_itens
        ],
        custos_fixos=v(b.custos_fixos),
        custos_fixos_pagos=facts.fixed_paid,
        custos_fixos_a_pagar=facts.fixed_pending,
        aporte_planejado=b.aporte_planejado,
        aporte_definido=b.aporte_definido,
        dividas=b.dividas,
        dividas_informadas=b.dividas_informadas,
        dividas_prefill=facts.consumed.dividas,
        disponivel=v(b.disponivel),
        consumido=v(b.consumido),
        restante=v(b.restante),
        consumo_financiado=v(b.consumo_financiado),
        financiado_objetivo=v(por_objetivo),
        financiado_carteira=v(por_carteira),
        restante_sem_resgates=v(b.restante_sem_resgates),
        gastos=facts.gastos,
        deducao_fixos=facts.consumed.fixos,
        deducao_dividas=facts.consumed.dividas,
        devolucoes=facts.consumed.devolucoes,
        investido=facts.investido,
        taxa_poupanca=(
            v((rate * _HUNDRED).quantize(_CENT))
            if rate is not None
            else Valued[Decimal](unavailable_reason="sem_receita", as_of=as_of, source="ledger")
        ),
        aporte_sobre_trabalho=(
            v(_pct(facts.investido, facts.trabalho))
            if facts.trabalho > 0
            else Valued[Decimal](unavailable_reason="sem_receita", as_of=as_of, source="ledger")
        ),
        # % sobre o total dos grupos (antes das devoluções): as linhas somam 100% e o rodapé mostra
        # total dos grupos − devoluções = consumido
        consumido_por_grupo=_groups(facts, groups_total),
        grupos_total=groups_total,
        investido_por_categoria=[
            ConsumedSub(name=name, value=x, pct=_pct(x, facts.investido), count=n)
            for name, (x, n) in sorted(facts.invested_by_category.items(), key=lambda i: -i[1][0])
        ],
        aporte_diferenca=b.aporte_planejado - facts.investido if b.aporte_definido else None,
        receitas_planejadas=planned,
        receita_planejada=planned_total,
        receita_a_receber=a_receber,
        disponivel_com_a_receber=v(b.disponivel + a_receber),
    )
