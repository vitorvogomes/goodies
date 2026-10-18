"""Painel principal (Stories 4.1 e 5.2 — FR-13): os KPIs vêm do resumo do mês de `closing`
(AD-8), que chama os termos de `ledger/calc` e `portfolio/calc` (AD-7). Cada número sai em `Valued`
com `as_of` = a data mais antiga das fontes que o geraram.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import asyncpg

from engines.closing import service as closing
from engines.common.dates import add_months, today_brt
from engines.common.models import Valued
from engines.common.owner import get_owner_id
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.market import service as market_service
from engines.portfolio import service as portfolio_service

from .models import Fonte, Painel


async def painel(conn: asyncpg.Connection, month: date) -> Painel:
    """KPIs do mês pelo resumo de `closing` (AD-8): o mesmo cálculo do fechamento."""
    pending = await ledger_service.pending_review_count(conn)
    summary = await closing.month_summary(conn, month)  # fechado → snapshot (5.5)
    previous = await closing.month_result(conn, add_months(month, -1))  # só o resultado
    if summary.ledger_as_of is not None:
        resultado = Valued[Decimal](
            value=summary.resultado_mes, as_of=summary.ledger_as_of, source="ledger"
        )
    else:
        resultado = Valued[Decimal](unavailable_reason="nao_definido")
    anterior = (
        Valued[Decimal](value=previous.value, as_of=previous.as_of, source="ledger")
        if previous is not None
        else Valued[Decimal](unavailable_reason="nao_definido")
    )
    variacao = (
        Valued[Decimal](
            value=summary.resultado_mes - previous.value,
            as_of=summary.ledger_as_of,
            source="ledger",
        )
        if resultado.value is not None and previous is not None
        else Valued[Decimal](unavailable_reason="nao_definido")
    )
    dates = [d for d in (summary.portfolio_as_of, summary.ledger_as_of) if d is not None]
    as_of = min(dates) if dates else None

    def portfolio_value(value: Decimal, when: date | None, term: str) -> Valued[Decimal]:
        if term in summary.unavailable:  # snapshot sem o termo: "—" com o tooltip (5.5)
            return Valued[Decimal](unavailable_reason="fora_do_resumo", source="snapshot")
        return Valued[Decimal](
            value=value, as_of=when, source="portfolio", stale=summary.portfolio_stale
        )

    return Painel(
        periodo=f"{month:%Y-%m}",
        resultado_mes=resultado,
        resultado_mes_anterior=anterior,
        variacao_resultado_mes=variacao,
        patrimonio=portfolio_value(summary.patrimonio, as_of, "patrimonio"),
        resultado_investimentos=portfolio_value(
            summary.resultado_investimentos, summary.portfolio_as_of, "resultado_investimentos"
        ),
        rentabilidade_nominal=(
            portfolio_value(summary.rentabilidade, summary.portfolio_as_of, "rentabilidade")
            if summary.rentabilidade is not None
            else Valued[Decimal](
                unavailable_reason="sem_preco", as_of=summary.portfolio_as_of, source="portfolio"
            )
        ),
        a_revisar=pending,
    )


# Limites das fontes automáticas: preço diário + fim de semana; scan 2×/dia; CDI dia útil.
_AUTO_LIMIT_DAYS = {"precos": 3, "carteiras": 1, "indices": 5}


async def fontes(conn: asyncpg.Connection) -> list[Fonte]:
    """Bloco Fontes do Painel: as 5 de arquivo (com a conferência da PF) e as automáticas."""
    today = today_brt()
    rows = [
        Fonte(**r.model_dump(), opens_hub=True) for r in await ingest_service.sources(conn, today)
    ]
    snap = await portfolio_service.portfolio_snapshot(conn, await get_owner_id(conn))
    auto = (
        ("precos", "Preços", snap.prices_as_of),
        ("carteiras", "Carteiras", snap.wallets_as_of),
        ("indices", "CDI/IPCA", await market_service.latest_index_date(conn)),
    )
    for key, label, until in auto:
        rows.append(
            Fonte(
                key=key,
                label=label,
                kind="automático",
                updated_until=until,
                stale=until is not None and (today - until).days > _AUTO_LIMIT_DAYS[key],
                opens_hub=False,
            )
        )
    return rows
