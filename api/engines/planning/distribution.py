"""Distribuição do aporte (Story 8.5 — FR-29, AD-12, AD-4): `distribute(planned, goals, targets,
positions, locks)`, pura, em ordem fixa:

1. **Reserva de emergência**: falta ÷ meses do horizonte, nunca além da falta (até encher).
2. **Demais objetivos**: falta ÷ meses até o prazo; faltando aporte, proporcional às necessidades.
3. **Classes** (base sem os objetivos — AD-11): piso de cada classe; pisos que não cabem são
   reduzidos em proporção; o resto vai pelo déficit em relação à meta depois do aporte —
   proporcional ao déficit (monotônico: maior déficit, maior sugestão); acima da banda, só o piso;
   déficits cobertos, a sobra segue a meta das classes que não estão acima da banda.
4. **Ativos**: dentro da classe, pelo déficit em relação à meta do ativo (cripto pelo valor atual);
   classe sem meta por ativo não divide.
5. **Lotes**: ativo com `Lot` (B3: cota inteira; Tesouro: 0,01 título com ordem mínima de R$ 30) só
   recebe o que se compra de fato — o valor vira cotas inteiras, arredondadas à mais próxima
   enquanto cabem na classe. O troco das classes segue os destinos em ordem (`troco_sinks`: a
   reserva até encher, a caixinha Turbo até o teto dela, o objetivo mais perto de ser concluído —
   objetivo travado não recebe); o que sobrar vai às classes de valor livre (sem lote) que não estão
   acima da banda, pelo déficit; sem nenhuma, fica sem destino.

Travas (`locks`, FR-30): `goal:<id>`, `class:<classe>`, `asset:<id>` entram fixas; o resto segue a
mesma regra. Nunca sugere venda. Cada nível fecha ao centavo pelo maior resto.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal

_CENT = Decimal("0.01")
_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class GoalNeed:
    id: str
    name: str
    kind: str  # reserva | objetivo
    target: Decimal
    current: Decimal
    months: int  # reserva: o horizonte; objetivo: meses até o prazo (≥ 1)
    deadline: date | None = None

    @property
    def missing(self) -> Decimal:
        return max(_ZERO, self.target - self.current)

    @property
    def monthly(self) -> Decimal:
        return self.missing / max(self.months, 1)


@dataclass(frozen=True)
class Lot:
    """Como o ativo se compra: incrementos de `qty` unidade a `price`, ordem mínima `minimum`."""

    price: Decimal  # preço de 1 unidade (cota, ação, título)
    qty: Decimal = Decimal(1)  # o incremento, em unidades (Tesouro: 0,01 título)
    minimum: Decimal = _ZERO  # ordem mínima em R$ (Tesouro: R$ 30)

    @property
    def step(self) -> Decimal:
        return self.price * self.qty

    @property
    def first_increments(self) -> int:
        """Incrementos da menor ordem possível (a ordem mínima arredondada para cima)."""
        if self.step <= 0:
            return 1
        return max(1, int((self.minimum / self.step).to_integral_value(rounding=ROUND_CEILING)))

    def cost(self, increments: int) -> Decimal:
        return (self.step * increments).quantize(_CENT)


TESOURO_MINIMUM = Decimal(30)


def tesouro_lot(price: Decimal) -> Lot:
    """Tesouro Direto: 1% do título por vez, respeitado o mínimo de R$ 30 por ordem."""
    return Lot(price, Decimal("0.01"), TESOURO_MINIMUM)


@dataclass(frozen=True)
class TrocoSink:
    """Um destino do troco das cotas: um objetivo, até `capacity` (None = até completar o alvo)."""

    goal_id: str
    label: str
    capacity: Decimal | None = None


@dataclass(frozen=True)
class AssetState:
    id: str
    label: str
    value: Decimal
    target_pct: Decimal | None  # meta dentro da classe (None = sem meta)
    lot: Lot | None = None  # None = valor livre (renda fixa, cripto): o sugerido segue ao centavo


@dataclass(frozen=True)
class ClassState:
    cls: str
    label: str
    value: Decimal
    target_pct: Decimal
    band_pp: Decimal
    floor: Decimal
    assets: Sequence[AssetState] = ()
    has_target: bool = True  # sem meta cadastrada: nunca "fora da banda" nem "só o piso"


@dataclass
class AssetLine:
    id: str
    label: str
    meta: Decimal | None
    atual: Decimal  # % dentro da classe
    sugerido: Decimal | None  # None = classe sem meta por ativo
    locked: bool = False
    preco: Decimal | None = None  # preço de 1 unidade (ativo com lote)
    cotas: Decimal | None = None  # unidades sugeridas (ativo com lote, sem trava)


@dataclass
class ClassLine:
    cls: str
    label: str
    meta: Decimal
    atual: Decimal  # % na base
    desvio: Decimal  # p.p.
    banda: Decimal
    floor: Decimal
    sugerido: Decimal
    floor_only: bool  # acima da banda: só o piso
    out_of_band: bool = False  # |desvio| > banda (o desvio sai em laranja)
    locked: bool = False
    assets: list[AssetLine] = field(default_factory=list)
    troco: Decimal = _ZERO  # o que as cotas inteiras dos ativos não usaram (sai da classe)
    recebido_troco: Decimal = _ZERO  # troco das cotas recebido (classe de valor livre)


@dataclass
class GoalLine:
    id: str
    name: str
    kind: str
    target: Decimal
    current: Decimal
    deadline: date | None
    monthly: Decimal  # o que falta por mês ("R$ 350/mês para chegar em jul/2027")
    sugerido: Decimal
    locked: bool = False
    recebido_troco: Decimal = _ZERO  # troco das cotas recebido (já somado no sugerido)


@dataclass
class Distribution:
    planned: Decimal
    goals: list[GoalLine]
    classes: list[ClassLine]
    floors_reduced: bool  # os pisos não couberam e foram reduzidos em proporção
    locks_total: Decimal  # Σ das travas (FR-30: acima do planejado → aviso)
    has_targets: bool  # sem metas, a distribuição das classes não tem base
    unassigned: Decimal = _ZERO  # sobra sem destino (tudo travado ou sem classes)
    troco: Decimal = _ZERO  # Σ do troco das cotas que teve destino (objetivos e classes livres)
    troco_destino: list[str] = field(default_factory=list)  # rótulos dos destinos, na ordem


def round_cents(raw: Mapping[str, Decimal], total: Decimal) -> dict[str, Decimal]:
    """Arredonda ao centavo pelo maior resto: a soma fecha exatamente em `total` (AD-4)."""
    floors = {k: max(_ZERO, v).quantize(_CENT, rounding=ROUND_DOWN) for k, v in raw.items()}
    left = int(((total - sum(floors.values(), _ZERO)) / _CENT).to_integral_value())
    order = sorted(raw, key=lambda k: (-(max(_ZERO, raw[k]) - floors[k]), list(raw).index(k)))
    for k in order[: max(left, 0)]:
        floors[k] += _CENT
    return floors


def _spread(amount: Decimal, weights: Mapping[str, Decimal]) -> dict[str, Decimal]:
    total = sum(weights.values(), _ZERO)
    if amount <= 0 or total <= 0:
        return {k: _ZERO for k in weights}
    return {k: amount * w / total for k, w in weights.items()}


def _fill(
    amount: Decimal, deficits: Mapping[str, Decimal], weights: Mapping[str, Decimal]
) -> dict[str, Decimal]:
    """Déficit primeiro (proporcional a ele — monotônico); coberto, a sobra segue os pesos."""
    need = sum(deficits.values(), _ZERO)
    if need >= amount:
        return _spread(amount, deficits)
    extra = _spread(amount - need, weights)
    return {k: deficits.get(k, _ZERO) + extra.get(k, _ZERO) for k in {**deficits, **weights}}


def distribute(
    planned: Decimal,
    goals: Sequence[GoalNeed],
    classes: Sequence[ClassState],
    locks: Mapping[str, Decimal] | None = None,
    troco_sinks: Sequence[TrocoSink] = (),
) -> Distribution:
    locks = dict(locks or {})
    remaining = planned
    raw: dict[str, Decimal] = {}

    # 1–2. Objetivos: travados fixos; a reserva primeiro, até encher; os demais pela necessidade
    goal_lines: list[GoalLine] = []
    reserve = [g for g in goals if g.kind == "reserva"]
    others = [g for g in goals if g.kind != "reserva"]
    for g in goals:
        key = f"goal:{g.id}"
        if key in locks:
            raw[key] = locks[key]
            remaining -= locks[key]
    for g in reserve:
        key = f"goal:{g.id}"
        if key not in locks:
            raw[key] = min(max(remaining, _ZERO), g.monthly, g.missing)
            remaining -= raw[key]
    free = [g for g in others if f"goal:{g.id}" not in locks]
    needs = {f"goal:{g.id}": min(g.monthly, g.missing) for g in free}
    if sum(needs.values(), _ZERO) <= max(remaining, _ZERO):
        raw.update(needs)
    else:
        raw.update(_spread(max(remaining, _ZERO), needs))
    remaining -= sum((raw[k] for k in needs), _ZERO)

    # 3. Classes
    has_targets = any(c.target_pct > 0 for c in classes)
    class_amount = max(remaining, _ZERO)
    total_value = sum((c.value for c in classes), _ZERO)
    after = total_value + class_amount
    floors_reduced = False
    unassigned = _ZERO
    class_raw: dict[str, Decimal] = {}
    if has_targets and classes:
        for c in classes:
            if f"class:{c.cls}" in locks:
                class_raw[c.cls] = locks[f"class:{c.cls}"]
        free_classes = [c for c in classes if c.cls not in class_raw]
        left = class_amount - sum(class_raw.values(), _ZERO)
        floors = {c.cls: c.floor for c in free_classes}
        if left <= 0:
            class_raw.update({c.cls: _ZERO for c in free_classes})
        elif sum(floors.values(), _ZERO) >= left:
            floors_reduced = sum(floors.values(), _ZERO) > left
            class_raw.update(_spread(left, floors))
        else:
            rest = left - sum(floors.values(), _ZERO)
            eligible = [c for c in free_classes if not _above_band(c, total_value)]
            deficits = {
                c.cls: max(_ZERO, c.target_pct / _HUNDRED * after - (c.value + c.floor))
                for c in eligible
            }
            weights = {c.cls: c.target_pct for c in (eligible or free_classes)}
            extra = _fill(rest, deficits, weights)
            if not weights or sum(weights.values(), _ZERO) <= 0:
                unassigned = rest
            class_raw.update({c.cls: c.floor + extra.get(c.cls, _ZERO) for c in free_classes})
    else:
        unassigned = class_amount

    top = {**{k: v for k, v in raw.items()}, **{f"class:{k}": v for k, v in class_raw.items()}}
    # o que tem destino fecha ao centavo; a sobra sem destino é o resto exato
    placed = (planned - unassigned).quantize(_CENT)
    unassigned = planned - placed
    rounded = round_cents(top, placed) if top else {}
    for g in goals:
        key = f"goal:{g.id}"
        goal_lines.append(
            GoalLine(
                id=g.id,
                name=g.name,
                kind=g.kind,
                target=g.target,
                current=g.current,
                deadline=g.deadline,
                monthly=g.monthly.quantize(_CENT),
                sugerido=rounded.get(key, _ZERO),
                locked=key in locks,
            )
        )

    # 4–5. Ativos, dentro do valor da classe, em cotas inteiras onde há lote
    class_lines: list[ClassLine] = []
    for c in classes:
        amount = rounded.get(f"class:{c.cls}", _ZERO)
        atual = c.value / total_value * _HUNDRED if total_value > 0 else _ZERO
        locked = f"class:{c.cls}" in locks
        assets, troco = _assets(c, amount, locks)
        if locked:
            troco = _ZERO  # a trava da classe vale: o troco fica nela, sem ativo
        class_lines.append(
            ClassLine(
                cls=c.cls,
                label=c.label,
                meta=c.target_pct,
                atual=atual.quantize(_CENT),
                desvio=(atual - c.target_pct).quantize(_CENT),
                banda=c.band_pp,
                floor=c.floor,
                sugerido=amount - troco,
                floor_only=_above_band(c, total_value),
                out_of_band=c.has_target
                and total_value > 0
                and abs(atual - c.target_pct) > c.band_pp,
                locked=locked,
                assets=assets,
                troco=troco,
            )
        )
    troco_total = sum((line.troco for line in class_lines), _ZERO)
    destino: list[str] = []
    left_troco = troco_total
    needs_by_id = {g.id: g for g in goals}
    for sink in troco_sinks:
        goal_line = next((x for x in goal_lines if x.id == sink.goal_id), None)
        need = needs_by_id.get(sink.goal_id)
        if left_troco <= 0 or goal_line is None or need is None or goal_line.locked:
            continue
        room = sink.capacity if sink.capacity is not None else need.missing - goal_line.sugerido
        gain = min(left_troco, max(_ZERO, room)).quantize(_CENT, rounding=ROUND_DOWN)
        if gain <= 0:
            continue
        goal_line.sugerido += gain
        goal_line.recebido_troco += gain
        left_troco -= gain
        destino.append(sink.label)
    if left_troco > 0:
        sinks = [
            (c, line)
            for c, line in zip(classes, class_lines, strict=True)
            if c.has_target
            and c.target_pct > 0
            and not line.locked
            and not line.floor_only
            and all(a.lot is None for a in c.assets)
        ]
        if sinks:
            sink_deficits = {
                c.cls: max(_ZERO, c.target_pct / _HUNDRED * after - c.value - line.sugerido)
                for c, line in sinks
            }
            share = round_cents(
                _fill(left_troco, sink_deficits, {c.cls: c.target_pct for c, _ in sinks}),
                left_troco,
            )
            for c, line in sinks:
                gain = share.get(c.cls, _ZERO)
                if gain <= 0:
                    continue
                line.recebido_troco = gain
                line.sugerido += gain
                line.assets, _ = _assets(c, line.sugerido, locks)
                destino.append(c.label)
            left_troco = _ZERO
        else:
            unassigned += left_troco  # o troco sem destino
    placed_troco = troco_total - max(left_troco, _ZERO)
    return Distribution(
        planned=planned,
        goals=goal_lines,
        classes=class_lines,
        floors_reduced=floors_reduced,
        locks_total=sum(locks.values(), _ZERO),
        has_targets=has_targets,
        unassigned=unassigned,
        troco=placed_troco,
        troco_destino=destino,
    )


def _above_band(c: ClassState, total: Decimal) -> bool:
    if total <= 0 or not c.has_target:
        return False
    return c.value / total * _HUNDRED - c.target_pct > c.band_pp


def _assets(
    c: ClassState, amount: Decimal, locks: Mapping[str, Decimal]
) -> tuple[list[AssetLine], Decimal]:
    """As linhas dos ativos e o troco da classe (o que as cotas inteiras não usaram)."""
    class_value = sum((a.value for a in c.assets), _ZERO)
    with_target = [a for a in c.assets if a.target_pct is not None and a.target_pct > 0]
    lines = [
        AssetLine(
            id=a.id,
            label=a.label,
            meta=a.target_pct,
            atual=(a.value / class_value * _HUNDRED).quantize(_CENT) if class_value > 0 else _ZERO,
            sugerido=None,
            locked=f"asset:{a.id}" in locks,
            preco=a.lot.price if a.lot is not None else None,
        )
        for a in c.assets
    ]
    if not with_target:
        # sem meta por ativo a classe não divide; só o ativo travado (aporte fixo) tem valor
        for line in lines:
            if line.locked:
                line.sugerido = locks[f"asset:{line.id}"].quantize(_CENT)
        return lines, _ZERO
    raw: dict[str, Decimal] = {}
    for a in c.assets:
        if f"asset:{a.id}" in locks:
            raw[a.id] = locks[f"asset:{a.id}"]
    left = max(_ZERO, amount - sum(raw.values(), _ZERO))
    after = class_value + amount
    free = [a for a in with_target if a.id not in raw]
    deficits = {
        a.id: max(_ZERO, (a.target_pct or _ZERO) / _HUNDRED * after - a.value) for a in free
    }
    raw.update(_fill(left, deficits, {a.id: a.target_pct or _ZERO for a in free}))
    lotted = [a for a in free if a.lot is not None and a.lot.price > 0]
    if not lotted:
        # com ativos livres com meta, a classe fecha ao centavo; tudo travado → as travas, exatas
        target = amount if free else sum(raw.values(), _ZERO).quantize(_CENT)
        rounded = round_cents(raw, max(target, sum(raw.values(), _ZERO).quantize(_CENT)))
        for line in lines:
            line.sugerido = rounded.get(line.id, _ZERO)
        return lines, _ZERO
    # Lotes: os ativos de valor livre ficam ao centavo; os de lote viram cotas inteiras
    others = {k: v for k, v in raw.items() if k not in {a.id for a in lotted}}
    exact = round_cents(others, sum(others.values(), _ZERO).quantize(_CENT)) if others else {}
    budget = amount - sum(exact.values(), _ZERO)
    whole = _whole_units({a.id: (a.lot, raw.get(a.id, _ZERO)) for a in lotted if a.lot}, budget)
    for line in lines:
        a = next(x for x in c.assets if x.id == line.id)
        if line.id in whole and a.lot is not None:
            n = whole[line.id]
            line.sugerido = a.lot.cost(n)
            line.cotas = units(a.lot, n)
        else:
            line.sugerido = exact.get(line.id, _ZERO)
    spent = sum((line.sugerido or _ZERO for line in lines), _ZERO)
    return lines, max(_ZERO, amount - spent)


def buy_units(wanted: Mapping[str, tuple[Lot, Decimal]], budget: Decimal) -> dict[str, int]:
    """A lista de compras de uma classe: o que falta do plano de cada ativo (R$), reduzido em
    proporção quando passa do que falta na classe, em incrementos inteiros."""
    total = sum((v for _, v in wanted.values()), _ZERO)
    if total <= 0 or budget <= 0:
        return {k: 0 for k in wanted}
    factor = min(Decimal(1), budget / total)
    return _whole_units({k: (lot, v * factor) for k, (lot, v) in wanted.items()}, budget)


def units(lot: Lot, increments: int) -> Decimal:
    """Unidades de `increments` incrementos (10 cotas; 0,03 título)."""
    return Decimal(increments) if lot.qty == 1 else (lot.qty * increments).quantize(lot.qty)


def _whole_units(wanted: Mapping[str, tuple[Lot, Decimal]], budget: Decimal) -> dict[str, int]:
    """Incrementos inteiros por ativo: primeiro o que o valor pedido compra inteiro; depois, com o
    que sobra, um incremento a mais onde a falta é ao menos meio incremento (a mais perto do pedido
    primeiro). Nunca passa do orçamento nem fica abaixo da ordem mínima."""
    n: dict[str, int] = {}
    for k, (lot, value) in wanted.items():
        whole = int((value / lot.step).to_integral_value(rounding=ROUND_DOWN))
        n[k] = whole if whole >= lot.first_increments else 0
    spent = sum((lot.cost(n[k]) for k, (lot, _) in wanted.items()), _ZERO)
    while spent > budget and any(n.values()):  # arredondamento de centavos acima do orçamento
        k = max((k for k in n if n[k]), key=lambda k: wanted[k][0].step)
        lot = wanted[k][0]
        n[k] = 0 if n[k] - 1 < lot.first_increments else n[k] - 1
        spent = sum((wanted[x][0].cost(n[x]) for x in n), _ZERO)
    while True:
        best: tuple[Decimal, str, int] | None = None
        for k, (lot, value) in wanted.items():
            nxt = n[k] + 1 if n[k] else lot.first_increments
            extra = lot.cost(nxt) - lot.cost(n[k])
            gap = value - lot.cost(n[k])
            if extra > budget - spent or gap < extra / 2:
                continue
            if best is None or gap - extra / 2 > best[0]:
                best = (gap - extra / 2, k, nxt)
        if best is None:
            return n
        _, k, nxt = best
        spent += wanted[k][0].cost(nxt) - wanted[k][0].cost(n[k])
        n[k] = nxt


# --------------------------------------------------------------------------------------------
# Entrada a partir da base (o serviço de `planning`; a função acima segue pura)
# --------------------------------------------------------------------------------------------


def months_until(month: date, deadline: date) -> int:
    """Meses do mês atual ao do prazo, contando os dois (prazo vencido → 1: falta tudo agora)."""
    return max(1, (deadline.year - month.year) * 12 + deadline.month - month.month + 1)
