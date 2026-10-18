"""Adapters da B3 no protocolo `SourceAdapter` (AD-5 — Story 3.8): movimentação, negociação e
consolidado (.xlsx).

- Movimentação/negociação viram `asset_operations` com dedup por `operation_hash` e a regra de
  cobertura por ticker (`_ticker_cutoffs`): por ticker só entra a cauda mais nova que o já coberto
  por outra proveniência; o resto é reportado como pulado. A liquidação já presente como negócio
  (ou o contrário) também é pulada (`_paired`). O `apply` refaz os dois cortes, então a mesma
  operação vinda dos dois arquivos, no mesmo lote ou em lotes diferentes, entra uma vez só.
- Consolidado grava `broker_position_snapshots` (data de referência, ativo, quantidade, valor) e
  aplica os preços das abas 'Posição' (precedência `is_manual`).
- O conteúdo não traz período: ele sai do nome do arquivo (movimentação/negociação: as datas do
  nome; consolidado mensal: o mês; anual: o ano, referência 31/12) e pode ser trocado na prévia
  (`overrides` `period_start`/`period_end`). Nome fora do padrão exige o período (`needs`).
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from engines.common.assets import CLASS_BY_CATEGORY, AssetCategory
from engines.common.owner import get_owner_id
from engines.ingest.protocol import Applied, FilePlan, ParsedFile, PlanError
from engines.market import service as market_service

from .b3_import import (
    parse_b3_movimentacao,
    parse_b3_negociacao,
    parse_b3_position_prices,
    parse_b3_positions,
)
from .b3_import_service import (
    _BROKER_BY_TYPE,
    _SHEET_BY_TYPE,
    _existing_category_map,
    _ticker_cutoffs,
)
from .b3_workbook import B3FileType, detect_file_type, load_workbook_sheets
from .migration import import_operations

_TYPE_BY_SOURCE: dict[str, B3FileType] = {
    "b3_movimentacao": "movimentacao",
    "b3_negociacao": "negociacao",
    "b3_consolidado": "consolidado",
}
_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_RANGE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")
_MONTHLY = re.compile(r"mensal-(\d{4})-([a-zç]+)", re.IGNORECASE)
_YEARLY = re.compile(r"anual-(\d{4})", re.IGNORECASE)


def period_from_name(file_name: str, ftype: B3FileType) -> tuple[date, date] | None:
    name = file_name.lower()
    if ftype in ("movimentacao", "negociacao"):
        m = _RANGE.search(name)
        if m:
            return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
        return None
    if (m := _MONTHLY.search(name)) and m.group(2) in _MONTHS:
        year, month = int(m.group(1)), _MONTHS[m.group(2)]
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if m := _YEARLY.search(name):
        return date(int(m.group(1)), 1, 1), date(int(m.group(1)), 12, 31)
    return None


# Liquidação (movimentação, D+2 úteis) × negócio (negociação): mesma operação até 7 dias corridos.
_PAIR_WINDOW_DAYS = 7
_OTHER_BROKERS = {
    "B3-movimentacao": ("B3-negociacao",),
    "B3-negociacao": ("B3-movimentacao", "Toro/B3"),
}


def _day_groups(items: list[dict[str, Any]]) -> dict[tuple[str, str, date], tuple[float, float]]:
    """(ticker, tipo, data) → (quantidade, valor) somados: a B3 liquida numa linha só os negócios
    do mesmo ticker no mesmo dia."""
    groups: dict[tuple[str, str, date], tuple[float, float]] = {}
    for it in items:
        key = (it["asset_symbol"], it["tipo"], it["data_operacao"])
        qty, total = groups.get(key, (0.0, 0.0))
        q = float(it["quantidade"])
        groups[key] = (qty + q, total + q * float(it["valor_unitario"]))
    return groups


async def _paired(
    conn: asyncpg.Connection, owner: str, ops: list[dict[str, Any]], broker: str
) -> set[str]:
    """`external_id` das compras/vendas que já estão na base pela outra fonte: mesmo ticker e tipo,
    mesma quantidade e valor somados no dia, e a liquidação até 7 dias depois do negócio. O hash não
    pega esse par (datas diferentes) e o corte por ticker também não, quando o negócio entrou
    antes."""
    trades = [op for op in ops if op["tipo"] in ("compra", "venda")]
    if not trades:
        return set()
    rows = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade, valor_unitario, data_operacao "
        "FROM asset_operations WHERE user_id = $1 AND broker = ANY($2::text[]) "
        "AND asset_symbol = ANY($3::text[]) AND tipo IN ('compra', 'venda')",
        owner,
        list(_OTHER_BROKERS[broker]),
        sorted({op["asset_symbol"] for op in trades}),
    )
    others = _day_groups([dict(r) for r in rows])
    settles_later = broker == "B3-movimentacao"
    used: set[tuple[str, str, date]] = set()
    paired_days: set[tuple[str, str, date]] = set()
    for key, (qty, total) in sorted(_day_groups(trades).items(), key=lambda kv: kv[0][2]):
        symbol, tipo, day = key
        for okey, (oqty, ototal) in others.items():
            if okey in used or okey[:2] != (symbol, tipo):
                continue
            delta = (day - okey[2]).days if settles_later else (okey[2] - day).days
            if (
                0 <= delta <= _PAIR_WINDOW_DAYS
                and abs(oqty - qty) < 1e-9
                and abs(ototal - total) <= 0.05
            ):
                used.add(okey)
                paired_days.add(key)
                break
    return {
        op["external_id"]
        for op in trades
        if (op["asset_symbol"], op["tipo"], op["data_operacao"]) in paired_days
    }


def _invalidate(ticker: str) -> Callable[[], Awaitable[None]]:
    async def run() -> None:
        await market_service.invalidate_price_cache(ticker)

    return run


_BATCH_PRICE_TICKERS = """
    SELECT DISTINCT a.price_ref FROM broker_position_snapshots s
    JOIN assets a ON a.id = s.asset_id
    JOIN asset_prices p ON p.ticker = a.price_ref AND p.source = 'b3' AND NOT p.is_manual
    WHERE s.batch_id = $1::uuid AND a.price_ref IS NOT NULL
"""
_PREVIOUS_SNAPSHOT = """
    SELECT s.quantity, s.reported_value, s.ref_date FROM broker_position_snapshots s
    JOIN assets a ON a.id = s.asset_id
    WHERE a.price_ref = $1 AND s.batch_id IS DISTINCT FROM $2::uuid AND s.quantity > 0
      AND s.reported_value IS NOT NULL
    ORDER BY s.ref_date DESC LIMIT 1
"""


def _price_day(day: date | None) -> datetime | None:
    """O preço do consolidado vale na data de referência dele (meio-dia em Brasília)."""
    if day is None:
        return None
    return datetime.combine(day, time(12), tzinfo=ZoneInfo("America/Sao_Paulo"))


def _chain(category: str) -> str:
    return "tesouro" if category == AssetCategory.APOSENTADORIA else "b3"


class B3Adapter:
    sources: tuple[str, ...] = ("b3_movimentacao", "b3_negociacao", "b3_consolidado")

    def detect(self, file_name: str, content: bytes) -> str | None:
        if not content.startswith(b"PK"):  # .xlsx é zip
            return None
        try:
            ftype = detect_file_type(load_workbook_sheets(content))
        except ValueError:
            return None
        return f"b3_{ftype}"

    def apply_rank(self, source: str) -> int:
        """Movimentação antes da negociação: a liquidação (D+2) cobre o negócio do mesmo trade, e o
        corte por ticker só deduplica nessa ordem."""
        return {"b3_movimentacao": 0, "b3_consolidado": 1, "b3_negociacao": 2}[source]

    def parse(self, source: str, file_name: str, content: bytes) -> dict[str, Any]:
        return {"sheets": load_workbook_sheets(content), "type": _TYPE_BY_SOURCE[source]}

    async def plan(
        self, conn: asyncpg.Connection, parsed: ParsedFile, overrides: dict[str, str]
    ) -> FilePlan:
        ftype: B3FileType = parsed.data["type"]
        plan = FilePlan(parsed.source, parsed.file_name, parsed.file_hash, parsed=parsed)
        plan.broker = _BROKER_BY_TYPE[ftype]
        period = period_from_name(parsed.file_name, ftype)
        try:
            if overrides.get("period_start") and overrides.get("period_end"):
                period = (
                    date.fromisoformat(overrides["period_start"]),
                    date.fromisoformat(overrides["period_end"]),
                )
        except ValueError:
            raise PlanError("Período escolhido inválido.") from None
        if period is None:
            plan.needs.append("period")
        else:
            plan.period_start, plan.period_end = period
        owner = await get_owner_id(conn)
        if ftype == "consolidado":
            await self._plan_snapshot(conn, plan, parsed.data["sheets"])
        else:
            await self._plan_operations(conn, plan, parsed.data["sheets"], ftype, owner)
        return plan

    async def _plan_operations(
        self,
        conn: asyncpg.Connection,
        plan: FilePlan,
        sheets: dict[str, Any],
        ftype: B3FileType,
        owner: str,
    ) -> None:
        rows = sheets.get(_SHEET_BY_TYPE[ftype]) or []
        category_map = await _existing_category_map(conn, owner)
        parse = parse_b3_movimentacao if ftype == "movimentacao" else parse_b3_negociacao
        ops = parse(rows, category_map)
        if not ops:
            raise PlanError("Nenhuma operação reconhecida no arquivo.")
        cutoffs = await _ticker_cutoffs(conn, owner, plan.broker or "")
        paired = await _paired(conn, owner, ops, plan.broker or "")
        kept = [
            op
            for op in ops
            if ((cut := cutoffs.get(op["asset_symbol"])) is None or op["data_operacao"] > cut)
            and op["external_id"] not in paired
        ]
        existing = {
            r["external_id"]
            for r in await conn.fetch(
                "SELECT external_id FROM asset_operations WHERE external_id = ANY($1::text[])",
                [op["external_id"] for op in kept],
            )
        }
        plan.rows = [op for op in kept if op["external_id"] not in existing]
        plan.new = len(plan.rows)
        plan.existing = len(kept) - plan.new
        plan.skipped = len(ops) - len(kept)
        plan.fingerprint = {"new_ids": sorted(op["external_id"] for op in plan.rows)}
        plan.detail = {
            "overlap_tickers": sorted(
                {op["asset_symbol"] for op in ops} - {op["asset_symbol"] for op in kept}
            ),
            "new_tickers": sorted({op["asset_symbol"] for op in kept} - set(category_map)),
            "paired": len(paired),
            "date_range": [
                min(op["data_operacao"] for op in ops).isoformat(),
                max(op["data_operacao"] for op in ops).isoformat(),
            ],
            "parsed": len(ops),
        }

    async def _plan_snapshot(
        self, conn: asyncpg.Connection, plan: FilePlan, sheets: dict[str, Any]
    ) -> None:
        positions = parse_b3_positions(sheets)
        prices = parse_b3_position_prices(sheets)
        if not positions and not prices:
            raise PlanError("Consolidado sem posições.")
        present: set[str] = set()
        if plan.period_end is not None:
            present = {
                f"{r['chain']}:{r['symbol']}"
                for r in await conn.fetch(
                    "SELECT a.chain, a.symbol FROM broker_position_snapshots s "
                    "JOIN asset_aliases a ON a.asset_id = s.asset_id WHERE s.ref_date = $1",
                    plan.period_end,
                )
            }
        plan.rows = [
            p for p in positions if f"{_chain(p['category'])}:{p['symbol']}" not in present
        ]
        plan.new = len(plan.rows)
        plan.existing = len(positions) - plan.new
        plan.fingerprint = {
            "positions": sorted((p["symbol"], p["quantity"], p["value"]) for p in plan.rows),
            "prices": sorted(prices.items()),
        }
        plan.detail = {"prices": prices, "parsed": len(positions)}

    async def apply(self, conn: asyncpg.Connection, plan: FilePlan, batch_id: str) -> Applied:
        assert plan.parsed is not None and plan.source is not None
        ftype: B3FileType = plan.parsed.data["type"]
        if ftype == "consolidado":
            return await self._apply_snapshot(conn, plan, batch_id)
        owner = await get_owner_id(conn)
        # Corte refeito: outro arquivo do mesmo lote pode ter coberto o ticker (AD-5).
        cutoffs = await _ticker_cutoffs(conn, owner, plan.broker or "")
        paired = await _paired(conn, owner, plan.rows, plan.broker or "")
        rows = [
            op
            for op in plan.rows
            if ((cut := cutoffs.get(op["asset_symbol"])) is None or op["data_operacao"] > cut)
            and op["external_id"] not in paired
        ]
        result = await import_operations(
            conn,
            owner,
            rows,
            broker_default=plan.broker or "B3",
            source=plan.source,
            batch_id=batch_id,
        )
        return Applied(
            inserted=result["imported"],
            months={op["data_operacao"].replace(day=1) for op in rows},
            detail={"skipped_overlap": plan.skipped + len(plan.rows) - len(rows)},
        )

    async def _apply_snapshot(
        self, conn: asyncpg.Connection, plan: FilePlan, batch_id: str
    ) -> Applied:
        inserted = 0
        if plan.period_end is not None:
            for p in plan.rows:
                category = p["category"]
                status = await conn.execute(
                    "INSERT INTO broker_position_snapshots "
                    "(ref_date, asset_id, quantity, reported_value, batch_id) "
                    "VALUES ($1, goodies_resolve_asset($2, $3, $4), $5, $6, $7::uuid) "
                    "ON CONFLICT (ref_date, asset_id) DO NOTHING",
                    plan.period_end,
                    _chain(category),
                    p["symbol"],
                    str(CLASS_BY_CATEGORY[category]),
                    p["quantity"],
                    p["value"],
                    batch_id,
                )
                inserted += int(status.split()[-1])
        upserted = 0
        written_tickers: list[str] = []
        newer = plan.period_end is not None and await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM broker_position_snapshots WHERE ref_date > $1)",
            plan.period_end,
        )
        # Preço só do consolidado mais recente, e nunca por cima de um preço buscado depois da data
        # de referência (ex.: o BRAPI diário): um arquivo antigo não sobrescreve o preço atual.
        prices = {} if newer else dict(plan.detail.get("prices", {}))
        if prices and plan.period_end is not None:
            fresher = {
                r["ticker"]
                for r in await conn.fetch(
                    "SELECT ticker FROM asset_prices WHERE ticker = ANY($1::text[]) "
                    "AND fetched_at::date > $2",
                    list(prices),
                    plan.period_end,
                )
            }
            prices = {t: p for t, p in prices.items() if t not in fresher}
        for ticker, price in prices.items():
            written = await market_service.upsert_price(
                conn, ticker, price, source="b3", is_manual=False, as_of=_price_day(plan.period_end)
            )
            if written:
                upserted += 1
                written_tickers.append(ticker)
        return Applied(
            inserted=inserted,
            detail={"prices_upserted": upserted},
            wrote_other=upserted > 0,
            # Depois do commit: invalidar antes deixaria uma leitura concorrente recachear o
            # preço velho (ainda não commitado o novo) por 26 h.
            after_commit=[_invalidate(t) for t in written_tickers],
        )

    async def undo_preview(self, conn: asyncpg.Connection, batch_id: str) -> dict[str, int]:
        return {
            "operations": int(
                await conn.fetchval(
                    "SELECT count(*) FROM asset_operations "
                    "WHERE batch_id = $1::uuid AND NOT protected",
                    batch_id,
                )
            ),
            "snapshots": int(
                await conn.fetchval(
                    "SELECT count(*) FROM broker_position_snapshots WHERE batch_id = $1::uuid",
                    batch_id,
                )
            ),
            "prices": len(await conn.fetch(_BATCH_PRICE_TICKERS, batch_id)),
        }

    async def undo(self, conn: asyncpg.Connection, batch_id: str) -> set[date]:
        months = {
            r["m"]
            for r in await conn.fetch(
                "SELECT DISTINCT date_trunc('month', data_operacao)::date AS m "
                "FROM asset_operations WHERE batch_id = $1::uuid AND NOT protected",
                batch_id,
            )
        }
        # Preço do consolidado desfeito volta ao do consolidado anterior (valor/quantidade).
        for r in await conn.fetch(_BATCH_PRICE_TICKERS, batch_id):
            previous = await conn.fetchrow(_PREVIOUS_SNAPSHOT, r["price_ref"], batch_id)
            if previous is not None:
                await market_service.upsert_price(
                    conn,
                    r["price_ref"],
                    float(previous["reported_value"]) / float(previous["quantity"]),
                    source="b3",
                    is_manual=False,
                    as_of=_price_day(previous["ref_date"]),
                )
                await market_service.invalidate_price_cache(r["price_ref"])
        await conn.execute(
            "DELETE FROM broker_position_snapshots WHERE batch_id = $1::uuid", batch_id
        )
        await conn.execute(
            "DELETE FROM asset_operations WHERE batch_id = $1::uuid AND NOT protected", batch_id
        )
        return months
