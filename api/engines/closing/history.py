"""Histórico do fluxo (Story 9.1 — FR-34, UX-DR9, UX-DR15): o período da leitura × o anterior × a
média 12m, em receitas, gastos por grupo, taxa de poupança e aporte planejado × realizado.

Cada mês vem do snapshot quando fechado e ao vivo (ledger + plano do mês) quando aberto; `as_of` é
o mais antigo e `stale` o OU dos meses; as razões são recalculadas dos componentes somados (nunca a
média das razões); nenhum mês depois do período entra. O anterior é a mesma leitura deslocada (o
mês, o trimestre ou o ano anterior, até a mesma altura); a média 12m é a dos 12 meses antes do
período, na escala do período. "Desde o início" não compara.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import asyncpg
from pydantic import BaseModel, Field

from engines.common.dates import (
    MIN_MONTH,
    add_months,
    month_end,
    parse_periodo,
    resolve_period,
    today_brt,
)
from engines.common.money import Money, Pct
from engines.common.shares import Slice, slices
from engines.ingest import service as ingest_service
from engines.ledger import service as ledger_service
from engines.planning.service import month_plan

from .models import MonthSource

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)
_SHIFT = {"mes": 1, "tri": 3, "ano": 12}


@dataclass
class Figures:
    receitas: Decimal = Decimal(0)
    trabalho: Decimal = Decimal(0)
    gastos: Decimal = Decimal(0)
    devolucoes: Decimal = Decimal(0)
    investido: Decimal = Decimal(0)
    planejado: Decimal | None = None  # Σ dos meses com aporte planejado (nenhum → None)
    por_grupo: dict[str, Decimal] = field(default_factory=dict)
    months: int = 0
    planned_months: int = 0  # meses com aporte planejado (a média do planejado é sobre eles)

    def add(self, other: Figures) -> None:
        self.receitas += other.receitas
        self.trabalho += other.trabalho
        self.gastos += other.gastos
        self.devolucoes += other.devolucoes
        self.investido += other.investido
        if other.planejado is not None:
            self.planejado = (self.planejado or Decimal(0)) + other.planejado
            self.planned_months += other.planned_months
        for k, v in other.por_grupo.items():
            self.por_grupo[k] = self.por_grupo.get(k, Decimal(0)) + v
        self.months += other.months

    def scaled(self, factor: Decimal) -> Figures:
        return Figures(
            receitas=self.receitas * factor,
            trabalho=self.trabalho * factor,
            gastos=self.gastos * factor,
            devolucoes=self.devolucoes * factor,
            investido=self.investido * factor,
            planejado=self.planejado * factor if self.planejado is not None else None,
            por_grupo={k: v * factor for k, v in self.por_grupo.items()},
            months=self.months,
        )

    @property
    def taxa_poupanca(self) -> Decimal | None:
        """Dos componentes somados: (trabalho − (gastos − devoluções)) ÷ trabalho, em %."""
        if self.trabalho <= 0:
            return None
        return (self.trabalho - (self.gastos - self.devolucoes)) / self.trabalho * _HUNDRED


class HistoryRow(BaseModel):
    key: str
    label: str
    kind: str  # money | pct
    current: Money | None
    previous: Money | None
    average: Money | None
    var_previous: Pct | None  # money: % sobre o anterior; pct: diferença em p.p.
    var_average: Pct | None


class History(BaseModel):
    periodo: str
    leitura: str
    months: list[MonthSource]
    as_of: date | None
    stale: bool
    previous_label: str | None  # "set/2026", "3º tri/2026"…; None = sem comparação
    average_months: int  # quantos meses entram na média 12m (0 = sem média)
    rows: list[HistoryRow]
    groups: list[HistoryRow]  # gastos por grupo, do maior para o menor no período
    # v2.2 (pizza): os gastos do período por grupo, com o % do total
    groups_share: list[Slice] = Field(default_factory=list)


def _var(kind: str, current: Decimal | None, ref: Decimal | None) -> Decimal | None:
    if current is None or ref is None:
        return None
    if kind == "pct":
        return (current - ref).quantize(_CENT)
    if ref == 0:
        return None
    return ((current - ref) / abs(ref) * _HUNDRED).quantize(_CENT)


def _q(value: Decimal | None) -> Decimal | None:
    return value.quantize(_CENT) if value is not None else None


def _row(
    key: str, label: str, kind: str, cur: Decimal | None, prev: Decimal | None, avg: Decimal | None
) -> HistoryRow:
    return HistoryRow(
        key=key,
        label=label,
        kind=kind,
        current=_q(cur),
        previous=_q(prev),
        average=_q(avg),
        var_previous=_var(kind, cur, prev),
        var_average=_var(kind, cur, avg),
    )


@dataclass
class _Month:
    figures: Figures
    source: str
    as_of: date | None
    stale: bool


async def _month(
    conn: asyncpg.Connection,
    month: date,
    groups: dict[str, tuple[str, str]],
    mei_until: date | None,
) -> _Month:
    from .service import latest_close, month_summary

    def by_group(per_category: dict[str, Decimal]) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for category, value in per_category.items():
            key = groups.get(category, ("sem_grupo", "Sem grupo"))[0]
            out[key] = out.get(key, Decimal(0)) + value
        return out

    close = await latest_close(conn, month)
    if close is not None and close["status"] == "closed":
        s = await month_summary(conn, month)
        f = Figures(
            receitas=s.receitas,
            trabalho=s.trabalho,
            gastos=s.gastos,
            devolucoes=s.devolucoes,
            investido=s.investido,
            planejado=s.aporte_planejado,
            por_grupo=by_group(s.gastos_por_categoria),
            months=1,
            planned_months=1 if s.aporte_planejado is not None else 0,
        )
        return _Month(f, "snapshot", s.as_of, False)
    ledger = await ledger_service.ledger_month(conn, month)
    plan = await month_plan(conn, month)
    as_of = min(month_end(month), today_brt())
    f = Figures(
        receitas=ledger.receitas,
        trabalho=ledger.trabalho,
        gastos=ledger.gastos,
        devolucoes=ledger.devolucoes,
        investido=ledger.investido,
        planejado=plan.aporte_planejado,
        por_grupo=by_group(ledger.gastos_por_categoria),
        months=1,
        planned_months=1 if plan.aporte_planejado is not None else 0,
    )
    # receita do trabalho vem do MEI: sem cobrir o mês, os números do mês estão defasados
    stale = mei_until is not None and mei_until < month_end(month) and as_of >= mei_until
    return _Month(f, "live", as_of, stale)


async def _sum(
    conn: asyncpg.Connection,
    months: list[date],
    groups: dict[str, tuple[str, str]],
    mei_until: date | None,
    cache: dict[date, _Month],
) -> tuple[Figures, list[_Month]]:
    total = Figures()
    parts: list[_Month] = []
    for m in months:
        if m not in cache:
            cache[m] = await _month(conn, m, groups, mei_until)
        total.add(cache[m].figures)
        parts.append(cache[m])
    return total, parts


def _previous_months(periodo: date, leitura: str) -> list[date] | None:
    if leitura not in _SHIFT:
        return None
    end = add_months(periodo, -_SHIFT[leitura])
    start = {"mes": end, "tri": date(end.year, (end.month - 1) // 3 * 3 + 1, 1)}.get(
        leitura, date(end.year, 1, 1)
    )
    if start < MIN_MONTH:  # o anterior começaria antes da base: sem comparação
        return None
    return resolve_period(f"{end:%Y-%m}", leitura)


def _label(months: list[date], leitura: str) -> str:
    from engines.common.dates import month_label

    end = months[-1]
    if leitura == "mes":
        return month_label(end)
    if leitura == "tri":
        return f"{(end.month - 1) // 3 + 1}º tri/{end.year}"
    return f"{end.year}"


async def history(conn: asyncpg.Connection, periodo: str, leitura: str) -> History:
    months = resolve_period(periodo, leitura)
    groups = await ledger_service.category_groups(conn)
    mei = next(
        (
            s
            for s in await ingest_service.sources(conn, today_brt(), with_balances=False)
            if s.key == "nubank_mei"
        ),
        None,
    )
    mei_until = mei.updated_until if mei is not None else None
    cache: dict[date, _Month] = {}
    current, parts = await _sum(conn, months, groups, mei_until, cache)
    previous: Figures | None = None
    previous_label: str | None = None
    average: Figures | None = None
    if leitura != "inicio":
        prev_months = _previous_months(parse_periodo(periodo), leitura)
        if prev_months:
            previous, _ = await _sum(conn, prev_months, groups, mei_until, cache)
            previous_label = _label(prev_months, leitura)
        start = months[0]
        window = [add_months(start, -i) for i in range(12, 0, -1)]
        window = [m for m in window if m >= MIN_MONTH]
        if window:
            avg_total, _ = await _sum(conn, window, groups, mei_until, cache)
            average = avg_total.scaled(Decimal(len(months)) / Decimal(len(window)))
            # o planejado só existe nos meses que tiveram plano: a média é sobre eles
            average.planejado = (
                avg_total.planejado / avg_total.planned_months * len(months)
                if avg_total.planejado is not None and avg_total.planned_months
                else None
            )
    rows = [
        _row(
            "receitas",
            "Receitas",
            "money",
            current.receitas,
            _g(previous, "receitas"),
            _g(average, "receitas"),
        ),
        _row(
            "trabalho",
            "Receita do trabalho",
            "money",
            current.trabalho,
            _g(previous, "trabalho"),
            _g(average, "trabalho"),
        ),
        _row(
            "gastos",
            "Gastos",
            "money",
            current.gastos,
            _g(previous, "gastos"),
            _g(average, "gastos"),
        ),
        _row(
            "taxa_poupanca",
            "Taxa de poupança",
            "pct",
            current.taxa_poupanca,
            previous.taxa_poupanca if previous else None,
            average.taxa_poupanca if average else None,
        ),
        _row(
            "aporte_planejado",
            "Aporte planejado",
            "money",
            current.planejado,
            _g(previous, "planejado"),
            _g(average, "planejado"),
        ),
        _row(
            "aporte_realizado",
            "Aporte realizado",
            "money",
            current.investido,
            _g(previous, "investido"),
            _g(average, "investido"),
        ),
    ]
    names = sorted(
        set(current.por_grupo) | set(previous.por_grupo if previous else {}),
        key=lambda n: -current.por_grupo.get(n, Decimal(0)),
    )
    group_names = {key: name for key, name in groups.values()}
    group_rows = [
        _row(
            f"grupo:{n}",
            group_names.get(n, "Sem grupo"),
            "money",
            current.por_grupo.get(n, Decimal(0)),
            previous.por_grupo.get(n, Decimal(0)) if previous else None,
            average.por_grupo.get(n, Decimal(0)) if average else None,
        )
        for n in names
    ]
    known = [p.as_of for p in parts if p.as_of is not None]
    return History(
        periodo=periodo,
        leitura=leitura,
        months=[MonthSource(month=m, source=p.source) for m, p in zip(months, parts, strict=True)],
        as_of=min(known) if known else None,
        stale=any(p.stale for p in parts),
        previous_label=previous_label,
        average_months=average.months if average else 0,
        rows=rows,
        groups=group_rows,
        groups_share=slices(
            (
                f"grupo:{n}",
                group_names.get(n, "Sem grupo"),
                current.por_grupo.get(n, Decimal(0)),
                None,
            )
            for n in names
        ),
    )


def _g(f: Figures | None, attr: str) -> Decimal | None:
    if f is None:
        return None
    value: Decimal | None = getattr(f, attr)
    return value
