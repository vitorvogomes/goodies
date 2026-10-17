"""Orquestra o import de um workbook B3 (3 tipos) -> asset_operations + preços.

Eleva a lógica de `scripts/import_b3.py` a um serviço reutilizável pelo endpoint.

Regra de cobertura (load-bearing): `operation_hash` NÃO deduplica o mesmo trade
entre fontes (negociação usa data do negócio; movimentação usa data de liquidação
D+2 -> hashes diferentes). Então, por ticker, importamos apenas a CAUDA mais nova
que o já-coberto por OUTRA proveniência (o `broker` etiqueta a fonte), e reportamos
o que foi pulado (`skipped_overlap`) — nunca trunca em silêncio.

Tipos:
- consolidado: aplica preços (abas 'Posição'); ops vêm de mov/neg. As categorias das
  abas NÃO são aplicadas (sobrescreveria correções manuais) — débito do hub de ingestão v2.
- movimentacao / negociacao: vira ops, sob a regra de cobertura.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg

from engines.market import service as market_service

from . import service
from .b3_import import (
    parse_b3_movimentacao,
    parse_b3_negociacao,
    parse_b3_position_prices,
)
from .b3_workbook import B3FileType, detect_file_type
from .migration import import_operations

_BROKER_BY_TYPE: dict[B3FileType, str] = {
    "movimentacao": "B3-movimentacao",
    "negociacao": "B3-negociacao",
    "consolidado": "B3-consolidado",
}
_SHEET_BY_TYPE: dict[B3FileType, str] = {
    "movimentacao": "Movimentação",
    "negociacao": "Negociação",
}


async def _existing_category_map(
    conn: asyncpg.Connection, user_id: str
) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT DISTINCT asset_symbol, asset_category FROM asset_operations "
        "WHERE user_id = $1",
        user_id,
    )
    return {r["asset_symbol"]: r["asset_category"] for r in rows}


async def _ticker_cutoffs(
    conn: asyncpg.Connection, user_id: str, this_broker: str
) -> dict[str, date]:
    """Última data já coberta por OUTRA proveniência, por ticker (regra de cobertura)."""
    rows = await conn.fetch(
        "SELECT asset_symbol, max(data_operacao) AS maxd FROM asset_operations "
        "WHERE user_id = $1 AND broker <> $2 GROUP BY asset_symbol",
        user_id,
        this_broker,
    )
    return {r["asset_symbol"]: r["maxd"] for r in rows}


async def import_b3_workbook(
    conn: asyncpg.Connection,
    user_id: str,
    sheets: dict[str, list[tuple[Any, ...]]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    ftype = detect_file_type(sheets)
    report: dict[str, Any] = {
        "file_type": ftype,
        "parsed": 0,
        "imported": 0,
        "skipped_duplicate": 0,
        "skipped_overlap": 0,
        "overlap_tickers": [],
        "new_tickers": [],
        "date_range": None,
        "prices_upserted": 0,
        "prices_skipped_manual": 0,
        "dry_run": dry_run,
    }

    # --- consolidado: preços (abas 'Posição'); ops vêm de mov/neg ---
    if ftype == "consolidado":
        prices = parse_b3_position_prices(sheets)
        if dry_run:
            # preview: quantos NÃO seriam gravados por já serem manuais (precedência)
            report["prices_upserted"] = len(prices)
            report["note"] = (
                "consolidado (dry-run): preços seriam aplicados; "
                "ops vêm de movimentação/negociação"
            )
            return report
        upserted = 0
        for ticker, price in prices.items():
            # upsert_price retorna {} quando a precedência is_manual ignora a escrita;
            # só conta (e invalida o cache Redis) o que de fato gravou. Achado C4.
            written = await service.upsert_price(
                conn, ticker, price, source="b3", is_manual=False
            )
            if written:
                upserted += 1
                # o preço é gravado no Postgres, mas get_price lê o Redis 1º: sem isto
                # um preço B3 cacheado (TTL 26h) mascararia o recém-importado. Achado C4.
                await market_service.invalidate_price_cache(ticker)
        report["prices_upserted"] = upserted
        report["prices_skipped_manual"] = len(prices) - upserted
        report["note"] = (
            "consolidado: preços aplicados; ops vêm de movimentação/negociação"
        )
        return report

    # --- movimentação / negociação: ops sob a regra de cobertura ---
    this_broker = _BROKER_BY_TYPE[ftype]
    rows = sheets.get(_SHEET_BY_TYPE[ftype]) or []
    category_map = await _existing_category_map(conn, user_id)
    if ftype == "movimentacao":
        ops = parse_b3_movimentacao(rows, category_map)
    else:
        ops = parse_b3_negociacao(rows, category_map)
    report["parsed"] = len(ops)
    if not ops:
        return report

    cutoffs = await _ticker_cutoffs(conn, user_id, this_broker)
    kept: list[dict[str, Any]] = []
    overlap_tickers: set[str] = set()
    new_tickers: set[str] = set()
    for op in ops:
        sym = op["asset_symbol"]
        cut = cutoffs.get(sym)
        if cut is not None and op["data_operacao"] <= cut:
            overlap_tickers.add(sym)
            continue
        kept.append(op)
        if sym not in category_map:
            new_tickers.add(sym)
    report["skipped_overlap"] = len(ops) - len(kept)
    report["overlap_tickers"] = sorted(overlap_tickers)
    report["new_tickers"] = sorted(new_tickers)
    if kept:
        ds = [op["data_operacao"] for op in kept]
        report["date_range"] = [min(ds).isoformat(), max(ds).isoformat()]

    if dry_run:
        # preview fiel: quantos dos 'kept' já existem pelo hash, sem gravar nada
        ext = [op["external_id"] for op in kept]
        existing_ids: set[str] = set()
        if ext:
            existing_ids = {
                r["external_id"]
                for r in await conn.fetch(
                    "SELECT external_id FROM asset_operations "
                    "WHERE user_id = $1 AND external_id = ANY($2::text[])",
                    user_id,
                    ext,
                )
            }
        would_dup = sum(1 for op in kept if op["external_id"] in existing_ids)
        report["imported"] = len(kept) - would_dup
        report["skipped_duplicate"] = would_dup
        return report

    result = await import_operations(conn, user_id, kept, broker_default=this_broker)
    report["imported"] = result["imported"]
    report["skipped_duplicate"] = result["skipped"]
    if result["imported"]:
        await service.invalidate_xirr_cache(user_id)
    return report
