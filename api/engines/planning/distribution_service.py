"""A Distribuição do aporte a partir da base (Story 8.5): o planejado e as travas do mês
(`month_plans`), os objetivos (`goals`), as metas do mês e as posições atuais sem os objetivos
(AD-11) → `distribution.distribute` (pura). Tudo calculado aqui; o front só mostra (AD-4)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
from pydantic import BaseModel, Field

from engines.common.assets import AssetClass
from engines.common.dates import today_brt
from engines.common.money import Money, Pct, to_usd
from engines.common.owner import get_owner_id
from engines.market import service as market_service
from engines.portfolio import opportunity as opportunity_engine
from engines.portfolio.positions import GOALS_BLOCK, month_units

from . import allocation, goals, targets
from . import fixed as fixed_service
from . import progress as progress_service
from .distribution import (
    AssetState,
    ClassLine,
    ClassState,
    GoalNeed,
    Lot,
    TrocoSink,
    buy_units,
    distribute,
    months_until,
    round_cents,
    tesouro_lot,
    units,
)
from .service import month_plan


class PreviewIn(BaseModel):
    mes: str
    planejado: Money | None = Field(default=None, ge=0)  # None = o do mês
    travas: dict[str, Money] | None = None  # None = as gravadas no mês
    oportunidade: bool | None = None  # v2.2: None = a escolha gravada no mês


class UsdLine(BaseModel):
    """Cripto em US$ (v2.2): o plano, o realizado e a falta da linha pela cotação do dólar."""

    sugerido: Money | None = None
    realizado: Money | None = None
    pendente: Money | None = None


class AssetOut(BaseModel):
    id: str
    label: str
    meta: Pct | None
    atual: Pct
    sugerido: Money | None
    locked: bool
    fixo: bool = False  # aporte fixo do mês (trava padrão; a do próprio mês vence)
    realizado: Money = Decimal(0)  # Story 8.7: só o que virou ativo no mês
    pendente: Money | None = None  # sugerido − realizado
    # Ativo com lote (B3, Tesouro): o preço de hoje, a unidade e o sugerido em unidades inteiras
    preco: Decimal | None = None
    unidade: str | None = None  # "cota" (B3) | "título" (Tesouro, em centésimos)
    cotas: Decimal | None = None  # o plano do mês (na posição do início do mês)
    cotas_realizadas: Decimal | None = None  # o que entrou no mês, em unidades
    # A comprar: o pendente da classe dividido de novo pela posição de agora (o que já entrou no
    # mês conta), em unidades inteiras — a lista de compras
    comprar: Money | None = None
    comprar_cotas: Decimal | None = None
    usd: UsdLine | None = None  # só cripto (v2.2)
    # v2.2 — oportunidade de mercado: os sinais (%; negativo = em baixa), o fator (0,75–1,25) e o
    # sugerido sem o ajuste (só com a oportunidade ligada)
    var_3m: Pct | None = None
    vs_pm: Pct | None = None
    dd_52w: Pct | None = None
    fator: Decimal | None = None
    sugerido_sem_ajuste: Money | None = None
    ajuste_oportunidade: Money | None = None  # sugerido − sem o ajuste (+ ganhou, − perdeu)


class ClassOut(BaseModel):
    cls: str
    label: str
    meta: Pct
    atual: Pct
    desvio: Pct
    banda: Pct
    floor: Money
    sugerido: Money
    floor_only: bool
    out_of_band: bool
    locked: bool
    assets: list[AssetOut]
    fixo: bool = False  # o valor da classe é o dos aportes fixos dos ativos dela
    realizado: Money = Decimal(0)
    pendente: Money = Decimal(0)
    troco: Money = Decimal(
        0
    )  # o que as cotas inteiras não usaram (sai da classe: ver troco_destino)
    recebido_troco: Money = Decimal(0)
    # A comprar no mês: Σ dos ativos (cotas inteiras) ou, sem divisão por ativo, o pendente inteiro
    comprar: Money = Decimal(0)
    comprar_troco: Money = Decimal(0)  # o pendente que não compra cota inteira agora
    usd: UsdLine | None = None  # só cripto (v2.2)


class GoalOut(BaseModel):
    id: str
    name: str
    kind: str
    target: Money
    current: Money
    progress: Pct
    deadline: date | None
    monthly: Money
    sugerido: Money
    locked: bool
    realizado: Money = Decimal(0)
    pendente: Money = Decimal(0)
    fixo: bool = False
    recebido_troco: Money = Decimal(0)  # troco das cotas (já no sugerido)


class Andamento(BaseModel):
    """Story 8.7: realizado total (com o a caminho), em ativo, a caminho e pendente do mês."""

    planned: Money
    realizado: Money
    em_ativo: Money
    a_caminho: Money
    pendente: Money
    pct_realizado: Pct | None  # realizado ÷ planejado
    # rodapé de conciliação: objetivos + classes (Σ sugerido, Σ pendente das linhas)
    sugerido_linhas: Money
    pendente_linhas: Money
    confere: bool  # Σ pendente das linhas = pendente total + a caminho (realizado ≤ planejado)
    # Barra de progresso: trechos em % do planejado (em ativo sólido, a caminho hachurado)
    pct_em_ativo: Pct
    pct_a_caminho: Pct


class DistributionOut(BaseModel):
    month: date
    aporte_definido: bool
    planned: Money
    goals: list[GoalOut]
    classes: list[ClassOut]
    floors_reduced: bool
    locks_total: Money
    locks_over: bool  # "Travas somam R$ {x}, acima do planejado."
    has_targets: bool
    unassigned: Money
    andamento: Andamento
    troco: Money = Decimal(0)  # Σ do troco das cotas que teve destino (objetivos e classes livres)
    troco_destino: list[str] = Field(default_factory=list)
    oportunidade: bool = False  # v2.2: a divisão entre os ativos pesou a variação do preço


def _usd_line(
    sugerido: Decimal | None, realizado: Decimal, pendente: Decimal | None, fx: Decimal
) -> UsdLine:
    return UsdLine(
        sugerido=to_usd(sugerido, fx),
        realizado=to_usd(realizado, fx),
        pendente=to_usd(pendente, fx),
    )


def with_crypto_usd(classes: list[ClassOut], fx: Decimal | None) -> list[ClassOut]:
    """A classe cripto e os ativos dela ganham as linhas em US$ (v2.2); sem cotação, nada."""
    if fx is None:
        return classes
    for c in classes:
        if c.cls != str(AssetClass.CRIPTO):
            continue
        c.usd = _usd_line(c.sugerido, c.realizado, c.pendente, fx)
        for a in c.assets:
            a.usd = _usd_line(a.sugerido, a.realizado, a.pendente, fx)
    return classes


_UNIT = {"b3": "cota", "td": "título"}
# A caixinha Turbo (na reserva) rende 115% do CDI até R$ 5 mil (P28): o 2º destino do troco.
TURBO_KEY = "caixinha:turbo"
TURBO_CAP = Decimal(5000)


def troco_sinks(
    needs: list[GoalNeed], turbo: tuple[str, str, Decimal] | None = None
) -> list[TrocoSink]:
    """A ordem do troco das cotas (pedido de 18/10/2026), na posição do início do mês (estável a
    cada depósito): 1. a reserva de emergência até encher; 2. a caixinha Turbo da reserva até o teto
    dela (`turbo` = objetivo, rótulo, valor no início do mês); 3. os objetivos do mais perto de ser
    concluído (maior % do alvo) ao mais longe — o travado é pulado e o troco segue ao próximo."""
    sinks: list[TrocoSink] = []
    reserve = next((g for g in needs if g.kind == "reserva"), None)
    if reserve is not None:
        sinks.append(TrocoSink(reserve.id, reserve.name))
        if turbo is not None and turbo[0] == reserve.id:
            sinks.append(TrocoSink(reserve.id, turbo[1], max(Decimal(0), TURBO_CAP - turbo[2])))
    open_goals = [g for g in needs if g.kind != "reserva" and g.target > 0 and g.missing > 0]
    open_goals.sort(key=lambda g: (-(g.current / g.target), g.missing))
    sinks.extend(TrocoSink(g.id, g.name) for g in open_goals)
    return sinks


def buy_list(
    cl: ClassLine,
    pending: Decimal,
    lots: dict[str, Lot],
    units_done: dict[str, Decimal],
    realized: dict[str, Decimal],
) -> tuple[dict[str, int], dict[str, Decimal], Decimal, Decimal]:
    """A lista de compras de uma classe: (incrementos por ativo com lote, R$ por ativo sem lote,
    total a comprar, troco que não compra cota inteira). Com lote, as cotas do plano menos as que
    entraram no mês (travado/fixo: o R$ que falta); sem lote, o R$ que falta — tudo dentro do que
    falta na classe. Sem plano por ativo, o pendente da classe inteiro."""
    wanted: dict[str, tuple[Lot, Decimal]] = {}
    free_left: dict[str, Decimal] = {}
    for al in cl.assets:
        if al.sugerido is None or al.sugerido <= 0:
            continue
        real = realized.get(al.id, Decimal(0))
        if al.id in lots and al.cotas is not None:
            missing_units = max(Decimal(0), al.cotas - units_done.get(al.id, Decimal(0)))
            wanted[al.id] = (lots[al.id], missing_units * lots[al.id].price)
        elif al.id in lots:
            wanted[al.id] = (lots[al.id], max(Decimal(0), al.sugerido - real))
        else:
            free_left[al.id] = max(Decimal(0), al.sugerido - real)
    if not wanted and not free_left:
        return {}, {}, pending, Decimal(0)
    free_total = sum(free_left.values(), Decimal(0))
    if free_total > pending:  # o que falta na classe manda: reduz em proporção
        free_left = round_cents(
            {k: v * pending / free_total for k, v in free_left.items()}, pending
        )
        free_total = pending
    n = buy_units(wanted, pending - free_total) if wanted else {}
    cost = sum((lots[k].cost(v) for k, v in n.items()), Decimal(0))
    return n, free_left, cost + free_total, pending - cost - free_total


def lot_for(key: str | None, price: Decimal | None) -> Lot | None:
    """B3 (ação, FII, ETF): cota inteira; Tesouro: 0,01 título, mínimo R$ 30; o resto é livre."""
    if key is None or price is None or price <= 0:
        return None
    prefix = key.split(":", 1)[0]
    if prefix == "b3":
        return Lot(price)
    if prefix == "td":
        return tesouro_lot(price)
    return None


def _share(part: Decimal, whole: Decimal) -> Decimal:
    """% de `part` em `whole`, entre 0 e 100 (a barra nunca passa do planejado)."""
    if whole <= 0:
        return Decimal(0)
    return min(Decimal(100), max(Decimal(0), part / whole * 100)).quantize(Decimal("0.01"))


async def month_locks(conn: asyncpg.Connection, month: date) -> dict[str, Decimal]:
    raw = await conn.fetchval("SELECT travas FROM month_plans WHERE month = $1", month)
    return {k: Decimal(str(v)) for k, v in (json.loads(raw) if raw else {}).items()}


async def preview(
    conn: asyncpg.Connection,
    month: date,
    planned: Decimal | None = None,
    locks: dict[str, Decimal] | None = None,
    opportunity: bool | None = None,
) -> DistributionOut:
    plan = await month_plan(conn, month)
    on = plan.oportunidade if opportunity is None else opportunity
    defined = planned is not None or plan.aporte_planejado is not None
    amount = planned if planned is not None else (plan.aporte_planejado or Decimal(0))
    month_travas = locks if locks is not None else await month_locks(conn, month)
    # aportes fixos: travas padrão de todo mês; a trava do próprio mês vence
    fixed = {
        k: v
        for k, v in (await fixed_service.month_fixed(conn, month)).items()
        if k not in month_travas
    }
    locks = {**fixed, **month_travas}

    goal_list = (await goals.list_goals(conn)).goals
    # a base é a posição antes do aporte do mês: o que entrou no mês sai dos valores, senão a
    # sugestão mudaria a cada aporte feito (e o plano pediria mais que o planejado)
    month_done = await progress_service.month_progress(conn, month)

    def before(value: Decimal, key: str) -> Decimal:
        return max(Decimal(0), value - month_done.by_line.get(key, Decimal(0)))

    needs = [
        GoalNeed(
            id=g.id,
            name=g.name,
            kind=g.kind,
            target=g.target,
            current=before(g.valor, f"goal:{g.id}"),
            months=(g.horizon_months or 12)
            if g.kind == "reserva"
            else months_until(month, g.deadline or month),
            deadline=g.deadline,
        )
        for g in goal_list
    ]
    owner = await get_owner_id(conn)
    class_rows = await targets.class_targets(conn, month=month)
    asset_rows = await targets.asset_targets(conn, month=month)
    labels = dict(targets.CLASS_LABELS)
    current = await allocation.current_classes(conn, owner, month)
    asset_ids = [a.asset_id for c in current for a in c.assets if a.asset_id]
    asset_rows_db = await conn.fetch(
        "SELECT id::text AS id, key, price_ref, valuation FROM assets WHERE id = ANY($1::uuid[])",
        asset_ids,
    )
    keys = {r["id"]: r["key"] for r in asset_rows_db}
    # v2.2: os sinais de mercado dos ativos com cotação (B3, Tesouro, cripto); os outros, neutros
    market = {
        r["id"]: r["price_ref"]
        for r in asset_rows_db
        if r["valuation"] == "mercado" and r["price_ref"]
    }
    sig = (
        await opportunity_engine.market_signals(
            conn,
            owner,
            sorted(set(market.values())),
            opportunity_engine.reference_day(month, today_brt()),
        )
        if on
        else {}
    )
    asset_signals = {aid: sig[t] for aid, t in market.items() if t in sig}
    factors = {aid: opportunity_engine.factor(sg) for aid, sg in asset_signals.items()}
    units_done = await month_units(conn, owner, month)
    lots: dict[str, Lot] = {}
    states: list[ClassState] = []
    for c in current:
        if c.key == GOALS_BLOCK:
            continue
        row = class_rows.get(c.key)
        own = asset_rows.get(c.key, {})

        for a in c.assets:
            lot = lot_for(keys.get(a.asset_id or ""), a.preco)
            if lot is not None:
                lots[a.asset_id or a.symbol] = lot
        states.append(
            ClassState(
                cls=c.key,
                label=labels.get(c.key, c.label),
                value=before(c.valor, f"class:{c.key}"),
                target_pct=Decimal(row["target_pct"]) if row else Decimal(0),
                band_pp=Decimal(row["band_pp"]) if row else Decimal(0),
                floor=Decimal(row["floor"]) if row else Decimal(0),
                has_target=row is not None,
                assets=[
                    AssetState(
                        id=a.asset_id or a.symbol,
                        label=a.symbol,
                        value=before(a.valor.value or Decimal(0), f"asset:{a.asset_id}"),
                        target_pct=own.get(a.asset_id or ""),
                        lot=lots.get(a.asset_id or a.symbol),
                        opportunity=factors.get(a.asset_id or "", Decimal(1)),
                    )
                    for a in c.assets
                ],
            )
        )
    # ativo fixo de um objetivo (uma caixinha): o valor fixo é do objetivo
    linked = await goals.linked_assets(conn)
    for k in [k for k in fixed if k.startswith("asset:") and k.split(":", 1)[1] in linked]:
        value = fixed.pop(k)
        locks.pop(k, None)
        goal_key = f"goal:{linked[k.split(':', 1)[1]]}"
        if goal_key not in month_travas:
            fixed[goal_key] = fixed.get(goal_key, Decimal(0)) + value
            locks[goal_key] = fixed[goal_key]
    # ativo fixo ainda sem posição entra na classe dele com valor zero (a primeira compra)
    held = {a.id for st in states for a in st.assets}
    missing = [k.split(":", 1)[1] for k in fixed if k.startswith("asset:")]
    missing = [i for i in missing if i not in held]
    if missing:
        rows = await conn.fetch(
            "SELECT id::text AS id, key, name, class FROM assets WHERE id = ANY($1::uuid[])",
            missing,
        )
        for r in rows:
            keys[r["id"]] = r["key"]
            for i, st in enumerate(states):
                if st.cls == r["class"]:
                    extra = AssetState(
                        id=r["id"], label=r["name"], value=Decimal(0), target_pct=None
                    )
                    states[i] = replace(st, assets=[*st.assets, extra])

    def own_fixed(st: ClassState) -> Decimal:
        return sum((fixed.get(f"asset:{a.id}", Decimal(0)) for a in st.assets), Decimal(0))

    # ativo fixo numa classe sem meta por ativo: a classe recebe só os fixos dela
    fixed_classes: set[str] = set()
    for st in states:
        if own_fixed(st) > 0 and not any((a.target_pct or 0) > 0 for a in st.assets):
            if f"class:{st.cls}" not in month_travas:
                locks[f"class:{st.cls}"] = own_fixed(st)
                fixed_classes.add(st.cls)
    turbo_row = await conn.fetchrow(
        "SELECT a.id::text AS id, a.name, a.key FROM assets a WHERE a.key = $1", TURBO_KEY
    )
    turbo = None
    if turbo_row is not None and turbo_row["id"] in linked:
        goal_assets = {a.asset_id: a for g in goal_list for a in g.assets}
        now = goal_assets.get(turbo_row["id"])
        turbo = (
            linked[turbo_row["id"]],
            goals.asset_label(turbo_row["key"], turbo_row["name"]),
            before(now.valor or Decimal(0) if now else Decimal(0), f"asset:{turbo_row['id']}"),
        )
    sinks = troco_sinks(needs, turbo)
    d = distribute(amount, needs, states, locks, sinks)
    # numa classe com metas por ativo, os fixos dos ativos dela cabem no valor da classe
    short = {
        f"class:{st.cls}": own_fixed(st)
        for st, cl in zip(states, d.classes, strict=True)
        if own_fixed(st) > cl.sugerido and f"class:{st.cls}" not in locks
    }
    if short:
        locks.update(short)
        fixed_classes.update(k.split(":", 1)[1] for k in short)
        d = distribute(amount, needs, states, locks, sinks)
    # v2.2: o sugerido de cada ativo sem o ajuste (mesmas travas e destinos), para mostrar o efeito
    without: dict[str, Decimal | None] = {}
    if factors:
        neutral = [
            replace(st, assets=[replace(a, opportunity=Decimal(1)) for a in st.assets])
            for st in states
        ]
        base = distribute(amount, needs, neutral, locks, sinks)
        without = {a.id: a.sugerido for c in base.classes for a in c.assets}
    progress = {g.id: g.progress for g in goal_list}
    sugerido = {f"goal:{g.id}": g.sugerido for g in d.goals}
    sugerido.update({f"class:{c.cls}": c.sugerido for c in d.classes})
    done = progress_service.summary(month_done, sugerido, amount)

    def line(key: str) -> tuple[Decimal, Decimal]:
        return done.lines.get(key, (Decimal(0), sugerido.get(key, Decimal(0))))

    # A lista de compras: o que falta do plano de cada ativo — com lote, as cotas do plano menos as
    # que entraram no mês (travado/fixo: o R$ que falta), em cotas inteiras; sem lote, o R$ que
    # falta — dentro do que falta na classe. Sem plano por ativo, o pendente da classe inteiro.
    to_buy = {
        cl.cls: buy_list(
            cl,
            max(Decimal(0), line(f"class:{cl.cls}")[1]),
            lots,
            units_done,
            {
                k.split(":", 1)[1]: v
                for k, v in month_done.by_line.items()
                if k.startswith("asset:")
            },
        )
        for cl in d.classes
    }

    def asset_line(a: Any, cls: str) -> AssetOut:
        real = month_done.by_line.get(f"asset:{a.id}", Decimal(0))
        pend = a.sugerido - real if a.sugerido is not None else None
        lot = lots.get(a.id)
        prefix = (keys.get(a.id) or "").split(":", 1)[0]
        n = to_buy[cls][0].get(a.id)
        free = to_buy[cls][1].get(a.id)
        done = units_done.get(a.id, Decimal(0))
        return AssetOut(
            **vars(a),
            fixo=f"asset:{a.id}" in fixed,
            realizado=real,
            pendente=pend,
            unidade=_UNIT.get(prefix) if lot is not None else None,
            cotas_realizadas=done.quantize(lot.qty) if lot is not None else None,
            comprar=lot.cost(n) if lot is not None and n is not None else free,
            comprar_cotas=units(lot, n) if lot is not None and n is not None else None,
            var_3m=sg.var_3m if (sg := asset_signals.get(a.id)) else None,
            vs_pm=sg.vs_pm if sg else None,
            dd_52w=sg.dd_52w if sg else None,
            fator=factors.get(a.id),
            sugerido_sem_ajuste=without.get(a.id) if a.id in factors else None,
            ajuste_oportunidade=(
                a.sugerido - w
                if a.id in factors
                and a.sugerido is not None
                and (w := without.get(a.id)) is not None
                else None
            ),
        )

    return DistributionOut(
        month=month,
        aporte_definido=defined,
        planned=amount,
        goals=[
            GoalOut(
                **{**vars(g), "progress": progress.get(g.id, Decimal(0))},
                realizado=line(f"goal:{g.id}")[0],
                pendente=line(f"goal:{g.id}")[1],
                fixo=f"goal:{g.id}" in fixed,
            )
            for g in d.goals
        ],
        classes=with_crypto_usd(
            [
                ClassOut(
                    **{k: v for k, v in vars(c).items() if k != "assets"},
                    assets=[asset_line(a, c.cls) for a in c.assets],
                    realizado=line(f"class:{c.cls}")[0],
                    pendente=line(f"class:{c.cls}")[1],
                    comprar=to_buy[c.cls][2],
                    comprar_troco=to_buy[c.cls][3],
                    fixo=c.cls in fixed_classes,
                )
                for c in d.classes
            ],
            await market_service.usd_brl(conn),
        ),
        floors_reduced=d.floors_reduced,
        locks_total=d.locks_total,
        locks_over=d.locks_total > amount,
        has_targets=d.has_targets,
        unassigned=d.unassigned,
        troco=d.troco,
        troco_destino=d.troco_destino,
        oportunidade=on,
        andamento=Andamento(
            planned=amount,
            realizado=done.realizado,
            em_ativo=done.em_ativo,
            a_caminho=done.a_caminho,
            pendente=done.pendente,
            pct_realizado=(done.realizado / amount * 100).quantize(Decimal("0.01"))
            if amount > 0
            else None,
            sugerido_linhas=sum(sugerido.values(), Decimal(0)),
            pendente_linhas=sum((p for _, p in done.lines.values()), Decimal(0)),
            confere=sum((p for _, p in done.lines.values()), Decimal(0))
            == done.pendente + done.a_caminho,
            pct_em_ativo=_share(done.em_ativo, amount),
            pct_a_caminho=min(
                Decimal(100) - _share(done.em_ativo, amount), _share(done.a_caminho, amount)
            ),
        ),
    )
