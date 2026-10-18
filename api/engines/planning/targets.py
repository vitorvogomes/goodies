"""Metas de alocação, bandas e pisos (Story 8.2 — FR-35, AD-11): `portfolio_targets` é de
`planning`. Meta por classe (`asset_id` nulo) e por ativo dentro da classe; banda (p.p.) e piso (R$)
por classe; vigência — salvar grava a versão a partir do mês atual (a anterior fecha no mês
anterior). Cada nível soma 100% (conferido aqui, nunca no navegador); o nível ativo é opcional
(classe sem metas por ativo).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import asyncpg
from pydantic import BaseModel, Field

from engines.common.assets import CLASS_BY_CATEGORY, AssetClass
from engines.common.dates import today_brt
from engines.common.money import Money, Pct
from engines.common.owner import get_owner_id

from .goals import asset_label, linked_assets

_HUNDRED = Decimal(100)
_CENT = Decimal("0.01")
CATEGORY_BY_CLASS: dict[str, str] = {str(c): str(k) for k, c in CLASS_BY_CATEGORY.items()}
CLASS_LABELS: tuple[tuple[str, str], ...] = (
    (AssetClass.ACOES_BR, "Ações Nacionais"),
    (AssetClass.ETFS, "ETFs"),
    (AssetClass.FIIS, "FIIs"),
    (AssetClass.RENDA_FIXA, "Renda Fixa"),
    (AssetClass.APOSENTADORIA, "Aposentadoria"),
    (AssetClass.CRIPTO, "Cripto"),
)


class InvalidTargets(Exception):
    def __init__(self, errors: list[SumError]) -> None:
        super().__init__("metas inválidas")
        self.errors = errors


class TargetAssetIn(BaseModel):
    asset_id: str
    pct: Decimal = Field(ge=0, le=100)


class TargetClassIn(BaseModel):
    cls: str
    pct: Decimal = Field(ge=0, le=100)
    band_pp: Decimal = Field(ge=0, le=100)
    floor: Decimal = Field(ge=0)
    assets: list[TargetAssetIn] = Field(default_factory=list)


class TargetsIn(BaseModel):
    classes: list[TargetClassIn]


class TargetAsset(BaseModel):
    asset_id: str
    label: str
    pct: Pct  # 0 = sem meta para o ativo


class TargetClass(BaseModel):
    cls: str
    label: str
    pct: Pct
    band_pp: Pct
    floor: Money
    assets: list[TargetAsset]


class TargetsOut(BaseModel):
    defined: bool  # False = nenhuma meta ("Sem metas, a distribuição do aporte não tem base.")
    valid_from: date | None
    classes: list[TargetClass]


class SumError(BaseModel):
    level: str  # "classes" ou a classe do nível de ativos
    total: Pct
    message: str  # "Soma em {x}%. Ajuste para 100%."


class PreviewOut(BaseModel):
    ok: bool
    errors: list[SumError]


def pct_text(value: Decimal) -> str:
    text = f"{value.quantize(_CENT):f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def check_sums(body: TargetsIn) -> list[SumError]:
    """Cada nível soma 100%: as classes; e os ativos da classe, quando ela tem meta por ativo."""
    errors: list[SumError] = []

    def check(level: str, values: list[Decimal]) -> None:
        total = sum(values, Decimal(0)).quantize(_CENT)
        if total != _HUNDRED:
            message = f"Soma em {pct_text(total)}%. Ajuste para 100%."
            errors.append(SumError(level=level, total=total, message=message))

    check("classes", [c.pct for c in body.classes])
    for c in body.classes:
        if any(a.pct > 0 for a in c.assets):
            check(c.cls, [a.pct for a in c.assets])
    return errors


async def _rows(conn: asyncpg.Connection, user_id: str, month: date) -> list[asyncpg.Record]:
    return list(
        await conn.fetch(
            "SELECT class, asset_id::text AS asset_id, target_pct, band_pp, floor, valid_from "
            "FROM portfolio_targets WHERE user_id = $1::uuid AND valid_from <= $2 "
            "AND (valid_to IS NULL OR valid_to >= $2)",
            user_id,
            month,
        )
    )


async def class_targets(
    conn: asyncpg.Connection, user_id: str | None = None, month: date | None = None
) -> dict[str, asyncpg.Record]:
    """Classe → a meta vigente no mês (pct, banda, piso)."""
    owner = user_id or await get_owner_id(conn)
    rows = await _rows(conn, owner, month or today_brt().replace(day=1))
    return {r["class"]: r for r in rows if r["asset_id"] is None}


async def asset_targets(
    conn: asyncpg.Connection, user_id: str | None = None, month: date | None = None
) -> dict[str, dict[str, Decimal]]:
    """Classe → {asset_id: % dentro da classe} vigentes no mês."""
    owner = user_id or await get_owner_id(conn)
    out: dict[str, dict[str, Decimal]] = {}
    for r in await _rows(conn, owner, month or today_brt().replace(day=1)):
        if r["asset_id"] is not None:
            out.setdefault(r["class"], {})[r["asset_id"]] = Decimal(r["target_pct"])
    return out


async def legacy_category_targets(conn: asyncpg.Connection, user_id: str) -> dict[str, float]:
    """Provider da tela v1 de alocação (`portfolio`, registrado em main.py): rótulo legado → %.
    Numa base anterior à revisão 0043 (os testes de migração medem o "antes"), a meta é a única
    linha por categoria."""
    try:
        rows = await class_targets(conn, user_id)
    except asyncpg.UndefinedColumnError:
        legacy = await conn.fetch(
            "SELECT category, target_pct FROM portfolio_targets WHERE user_id = $1::uuid", user_id
        )
        return {r["category"]: float(r["target_pct"]) for r in legacy}
    return {CATEGORY_BY_CLASS[c]: float(r["target_pct"]) for c, r in rows.items()}


async def get_targets(conn: asyncpg.Connection) -> TargetsOut:
    owner = await get_owner_id(conn)
    month = today_brt().replace(day=1)
    rows = await _rows(conn, owner, month)
    by_class = {r["class"]: r for r in rows if r["asset_id"] is None}
    by_asset = {r["asset_id"]: Decimal(r["target_pct"]) for r in rows if r["asset_id"]}
    linked = await linked_assets(conn)  # ativos de objetivos ficam fora da alocação (AD-11)
    candidates = await conn.fetch(
        "SELECT id::text AS id, key, name, class FROM assets WHERE is_active "
        "AND key <> 'caixinha:encerradas' ORDER BY name"
    )
    classes: list[TargetClass] = []
    for cls, label in CLASS_LABELS:
        row = by_class.get(str(cls))
        classes.append(
            TargetClass(
                cls=str(cls),
                label=label,
                pct=Decimal(row["target_pct"]) if row else Decimal(0),
                band_pp=Decimal(row["band_pp"]) if row else Decimal(5),
                floor=Decimal(row["floor"]) if row else Decimal(0),
                assets=[
                    TargetAsset(
                        asset_id=a["id"],
                        label=asset_label(a["key"], a["name"]),
                        pct=by_asset.get(a["id"], Decimal(0)),
                    )
                    for a in candidates
                    if a["class"] == str(cls) and a["id"] not in linked
                ],
            )
        )
    valid_from = max((r["valid_from"] for r in rows), default=None)
    return TargetsOut(defined=bool(by_class), valid_from=valid_from, classes=classes)


async def _check_assets(conn: asyncpg.Connection, body: TargetsIn) -> None:
    """Cada meta por ativo é de um ativo da própria classe e fora dos objetivos (AD-11)."""
    wanted = {a.asset_id: c.cls for c in body.classes for a in c.assets if a.pct > 0}
    if not wanted:
        return
    try:
        ids = [str(uuid.UUID(a)) for a in wanted]
    except ValueError:
        raise InvalidTargets([]) from None
    classes = {
        r["id"]: r["class"]
        for r in await conn.fetch(
            "SELECT id::text AS id, class FROM assets WHERE id = ANY($1::uuid[])", ids
        )
    }
    linked = await linked_assets(conn)
    if any(classes.get(a) != cls or a in linked for a, cls in wanted.items()):
        raise InvalidTargets([])


async def save_targets(conn: asyncpg.Connection, body: TargetsIn) -> TargetsOut:
    """Grava a versão das metas a partir do mês atual (a vigente antes fecha no mês anterior)."""
    errors = check_sums(body)
    known = {str(c) for c, _ in CLASS_LABELS}
    if errors or any(c.cls not in known for c in body.classes):
        raise InvalidTargets(errors)
    await _check_assets(conn, body)
    owner = await get_owner_id(conn)
    month = today_brt().replace(day=1)
    async with conn.transaction():
        await conn.execute(
            "UPDATE portfolio_targets SET valid_to = $2 WHERE user_id = $1::uuid "
            "AND valid_from < $3 AND (valid_to IS NULL OR valid_to >= $3)",
            owner,
            month - timedelta(days=1),
            month,
        )
        await conn.execute(
            "DELETE FROM portfolio_targets WHERE user_id = $1::uuid AND valid_from = $2",
            owner,
            month,
        )
        insert = (
            "INSERT INTO portfolio_targets (user_id, category, asset_id, target_pct, band_pp, "
            "floor, valid_from) VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7)"
        )
        for c in body.classes:
            category = CATEGORY_BY_CLASS[c.cls]
            await conn.execute(insert, owner, category, None, c.pct, c.band_pp, c.floor, month)
            for a in c.assets:
                if a.pct > 0:
                    await conn.execute(
                        insert, owner, category, a.asset_id, a.pct, Decimal(0), Decimal(0), month
                    )
    return await get_targets(conn)
