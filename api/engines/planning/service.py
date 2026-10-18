"""Engine `planning` (camada 4): plano do mês (`month_plans`) e o orçamento pelos termos de
`planning/calc` sobre os fatos de `ledger` (AD-7). Num mês fechado o plano é só leitura (AD-8)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.common.models import Valued
from engines.common.month_status import month_status
from engines.ledger import service as ledger_service

from . import calc
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


async def ensure_month_plan(conn: asyncpg.Connection, month: date, *, mode: str) -> MonthPlanOut:
    """Plano do mês para o fechamento (Story 6.8). `retro`: dívidas = Σ das transações de role
    `divida` não casadas a custo fixo; aporte planejado nulo (`nao_definido`). Caminho de serviço
    do `refechar`/`close_retro` — por isso não passa pela trava de mês fechado."""
    if mode != "retro":
        raise ValueError(mode)
    facts = await ledger_service.budget_facts(conn, month)
    await conn.execute(
        "INSERT INTO month_plans (month, dividas, aporte_planejado) VALUES ($1, $2, NULL) "
        "ON CONFLICT (month) DO UPDATE SET dividas = EXCLUDED.dividas, aporte_planejado = NULL, "
        "updated_at = now()",
        month,
        facts.consumed.dividas,
    )
    return await month_plan(conn, month)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    return (part / whole * _HUNDRED).quantize(_CENT) if whole else Decimal(0)


def _groups(
    by_category: dict[tuple[str, str], tuple[Decimal, int]], total: Decimal
) -> list[ConsumedGroup]:
    groups: dict[str, list[tuple[str, Decimal, int]]] = {}
    for (group, sub), (value, n) in by_category.items():
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
        )
        for g, subs in groups.items()
    ]
    return sorted(out, key=lambda g: -g.value)


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

    def v(value: Decimal) -> Valued[Decimal]:
        return Valued[Decimal](value=value, as_of=as_of, source="ledger")

    rate = facts.taxa_poupanca
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
            ResgateItem(date=d, description=desc, value=x) for d, desc, x in facts.resgates_itens
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
        consumido_por_grupo=_groups(facts.by_category, facts.consumed.total),
    )
