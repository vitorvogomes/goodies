"""Migração de OPERAÇÕES (planilha CSV) -> asset_operations (STORY-02-17-18).

Lógica testável (parsing + import idempotente) separada do CLI
(`scripts/migrate_portfolio.py`). Adapta-se ao schema REAL implementado em
`0007_portfolio` (tipo compra/venda/...; quantidade>0; sem coluna total_amount).

Mapeamentos:
- categoria da planilha -> categoria canônica (casa com portfolio_targets/asset_category)
- tipo buy/sell/income -> compra/venda/dividendo (pt-br passa direto)
- Renda Fixa sem quantidade -> quantidade=1, valor_unitario=total
- idempotência: external_id = sha1(data, ticker, tipo, total)

Tickers são preservados como na planilha (ex.: PETR4F) para identificação correta.
"""
from __future__ import annotations

import csv
import hashlib
import io
import unicodedata
from datetime import date, datetime
from typing import Any

import asyncpg

from .constants import AssetCategory

# Categoria da planilha (upper, sem acento) -> categoria canônica (SSOT em constants.py)
CATEGORY_MAP: dict[str, str] = {
    "ACOES": AssetCategory.ACOES,
    "ACAO": AssetCategory.ACOES,
    "ACOESNACIONAIS": AssetCategory.ACOES,
    "ETF": AssetCategory.ETFS,
    "ETFS": AssetCategory.ETFS,
    "FII": AssetCategory.FIIS,
    "FIIS": AssetCategory.FIIS,
    "RENDAFIXA": AssetCategory.RENDA_FIXA,
    "RENDA_FIXA": AssetCategory.RENDA_FIXA,
    "RF": AssetCategory.RENDA_FIXA,
    "APOSENTADORIA": AssetCategory.APOSENTADORIA,
    "TESOURO": AssetCategory.APOSENTADORIA,
    "CRIPTO": AssetCategory.CRIPTO,
    "CRYPTO": AssetCategory.CRIPTO,
}

TIPO_MAP: dict[str, str] = {
    "buy": "compra",
    "sell": "venda",
    "income": "dividendo",
    "compra": "compra",
    "venda": "venda",
    "dividendo": "dividendo",
    "juros": "juros",
    "aporte": "aporte",
    "resgate": "resgate",
}

# Aliases de cabeçalho (sem acento, lower) -> campo canônico
_HEADER_ALIASES: dict[str, str] = {
    "data": "data",
    "date": "data",
    "ticker": "ticker",
    "ativo": "ticker",
    "simbolo": "ticker",
    "categoria": "categoria",
    "category": "categoria",
    "tipo": "tipo",
    "type": "tipo",
    "operacao": "tipo",
    "quantidade": "quantidade",
    "qtd": "quantidade",
    "quantity": "quantidade",
    "precounitario": "preco_unitario",
    "preco": "preco_unitario",
    "precounit": "preco_unitario",
    "valorunitario": "preco_unitario",
    "unitprice": "preco_unitario",
    "total": "total",
    "valortotal": "total",
    "totalamount": "total",
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_category(raw: str) -> str:
    """Categoria da planilha -> categoria canônica (passthrough se desconhecida)."""
    key = _strip_accents(raw).strip().upper().replace(" ", "").replace("-", "")
    return CATEGORY_MAP.get(key, raw.strip())


def normalize_tipo(raw: str) -> str:
    """tipo buy/sell/income (ou pt-br) -> tipo canônico de asset_operations."""
    key = _strip_accents(raw).strip().lower()
    if key not in TIPO_MAP:
        raise ValueError(f"tipo desconhecido: {raw!r}")
    return TIPO_MAP[key]


def parse_date(raw: str) -> date:
    """Aceita ISO (YYYY-MM-DD) ou BR (DD/MM/YYYY)."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {raw!r}")


def operation_hash(
    data_operacao: date, ticker: str, tipo: str, total: float
) -> str:
    """Hash idempotente de (data, ticker, tipo, total)."""
    payload = f"{data_operacao.isoformat()}|{ticker}|{tipo}|{total:.2f}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    txt = raw.strip().replace(" ", "")
    if not txt:
        return None
    # aceita 1.234,56 (BR) e 1234.56 (ISO)
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    return float(txt)


def _normalize_headers(fieldnames: list[str]) -> dict[str, str]:
    """Mapeia o nome real de coluna -> campo canônico."""
    mapping: dict[str, str] = {}
    for name in fieldnames:
        key = _strip_accents(name).strip().lower().replace(" ", "").replace("_", "")
        if key in _HEADER_ALIASES:
            mapping[name] = _HEADER_ALIASES[key]
    return mapping


def parse_operations_csv(text: str) -> list[dict[str, Any]]:
    """Parseia o CSV da aba OPERAÇÕES em linhas prontas para asset_operations."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    header_map = _normalize_headers(list(reader.fieldnames))

    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        row = {header_map.get(k, k): v for k, v in raw_row.items()}
        if not row.get("ticker"):
            continue
        data_operacao = parse_date(row["data"])
        ticker = row["ticker"].strip()
        tipo = normalize_tipo(row["tipo"])
        category = normalize_category(row.get("categoria", ""))
        qty = _to_float(row.get("quantidade"))
        preco = _to_float(row.get("preco_unitario"))
        total = _to_float(row.get("total"))

        # Renda Fixa / valor sem quantidade -> quantidade=1, valor_unitario=total
        if qty is None or qty == 0:
            quantidade = 1.0
            valor_unitario = total if total is not None else (preco or 0.0)
        else:
            quantidade = qty
            valor_unitario = preco if preco is not None else (
                (total / qty) if total is not None else 0.0
            )

        total_for_hash = total if total is not None else quantidade * valor_unitario
        rows.append(
            {
                "asset_symbol": ticker,
                "asset_category": category,
                "tipo": tipo,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "data_operacao": data_operacao,
                "external_id": operation_hash(
                    data_operacao, ticker, tipo, total_for_hash
                ),
            }
        )
    return rows


async def import_operations(
    conn: asyncpg.Connection,
    user_id: str,
    rows: list[dict[str, Any]],
    broker_default: str = "Migração",
) -> dict[str, int]:
    """Insere operações idempotentemente (ON CONFLICT external_id DO NOTHING).

    Retorna {"imported": N, "skipped": M} (skipped = já existentes pelo hash).
    """
    imported = 0
    skipped = 0
    for row in rows:
        result = await conn.execute(
            """
            INSERT INTO asset_operations
              (user_id, broker, asset_symbol, asset_category, tipo, quantidade,
               valor_unitario, data_operacao, external_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO NOTHING
            """,
            user_id,
            broker_default,
            row["asset_symbol"],
            row["asset_category"],
            row["tipo"],
            row["quantidade"],
            row["valor_unitario"],
            row["data_operacao"],
            row["external_id"],
        )
        if result.endswith("1"):
            imported += 1
        else:
            skipped += 1
    return {"imported": imported, "skipped": skipped}
