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

Travas (`locks`, FR-30): `goal:<id>`, `class:<classe>`, `asset:<id>` entram fixas; o resto segue a
mesma regra. Nunca sugere venda. Cada nível fecha ao centavo pelo maior resto.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal

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
class AssetState:
    id: str
    label: str
    value: Decimal
    target_pct: Decimal | None  # meta dentro da classe (None = sem meta)


@dataclass(frozen=True)
class ClassState:
    cls: str
    label: str
    value: Decimal
    target_pct: Decimal
    band_pp: Decimal
    floor: Decimal
    assets: Sequence[AssetState] = ()


@dataclass
class AssetLine:
    id: str
    label: str
    meta: Decimal | None
    atual: Decimal  # % dentro da classe
    sugerido: Decimal | None  # None = classe sem meta por ativo
    locked: bool = False


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


@dataclass
class Distribution:
    planned: Decimal
    goals: list[GoalLine]
    classes: list[ClassLine]
    floors_reduced: bool  # os pisos não couberam e foram reduzidos em proporção
    locks_total: Decimal  # Σ das travas (FR-30: acima do planejado → aviso)
    has_targets: bool  # sem metas, a distribuição das classes não tem base
    unassigned: Decimal = _ZERO  # sobra sem destino (tudo travado ou sem classes)


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
    rounded = round_cents(top, planned - unassigned) if top else {}
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

    # 4. Ativos, dentro do valor da classe
    class_lines: list[ClassLine] = []
    for c in classes:
        amount = rounded.get(f"class:{c.cls}", _ZERO)
        atual = c.value / total_value * _HUNDRED if total_value > 0 else _ZERO
        class_lines.append(
            ClassLine(
                cls=c.cls,
                label=c.label,
                meta=c.target_pct,
                atual=atual.quantize(_CENT),
                desvio=(atual - c.target_pct).quantize(_CENT),
                banda=c.band_pp,
                floor=c.floor,
                sugerido=amount,
                floor_only=_above_band(c, total_value),
                out_of_band=abs(atual - c.target_pct) > c.band_pp and total_value > 0,
                locked=f"class:{c.cls}" in locks,
                assets=_assets(c, amount, locks),
            )
        )
    return Distribution(
        planned=planned,
        goals=goal_lines,
        classes=class_lines,
        floors_reduced=floors_reduced,
        locks_total=sum(locks.values(), _ZERO),
        has_targets=has_targets,
        unassigned=unassigned,
    )


def _above_band(c: ClassState, total: Decimal) -> bool:
    if total <= 0:
        return False
    return c.value / total * _HUNDRED - c.target_pct > c.band_pp


def _assets(c: ClassState, amount: Decimal, locks: Mapping[str, Decimal]) -> list[AssetLine]:
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
        )
        for a in c.assets
    ]
    if not with_target:
        return lines
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
    rounded = round_cents(raw, max(amount, sum(raw.values(), _ZERO).quantize(_CENT)))
    for line in lines:
        line.sugerido = rounded.get(line.id, _ZERO)
    return lines


# --------------------------------------------------------------------------------------------
# Entrada a partir da base (o serviço de `planning`; a função acima segue pura)
# --------------------------------------------------------------------------------------------


def months_until(month: date, deadline: date) -> int:
    """Meses do mês atual ao do prazo, contando os dois (prazo vencido → 1: falta tudo agora)."""
    return max(1, (deadline.year - month.year) * 12 + deadline.month - month.month + 1)
