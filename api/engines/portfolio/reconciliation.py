"""Conciliação (Story 7.9 — FR-26, AD-13): as posições do app × o consolidado B3 e × o scan das
carteiras, por quantidade, com as tolerâncias de `calc` (QTY_TOLERANCE). Caixinhas e debêntures não
têm origem: "valor calculado". A conciliação carteira × operações (`net_quantity`) é do portfolio
(AD-1: o `wallet` não importa o `portfolio`).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
from pydantic import BaseModel

from engines.common.alerts import Alert, AlertAction, AlertContext, fingerprint
from engines.common.assets import CRYPTO_CATEGORIES
from engines.common.dates import month_end, month_label
from engines.common.numbers import value_of
from engines.common.owner import get_owner_id
from engines.wallet import service as wallet_service

from . import calc
from .service import net_quantity

SCAN_MAX_AGE = timedelta(hours=14)  # AD-13: aviso se o scan tiver mais de 14 h
_B3_CLASSES = ("acoes_br", "etfs", "fiis", "aposentadoria")
_BRT = "America/Sao_Paulo"


class ReconRow(BaseModel):
    symbol: str
    cls: str
    app: Decimal
    origin: Decimal | None
    diff: Decimal | None
    status: str  # conferido | divergente | valor calculado
    nota: str | None = None  # a diferença explicada (fração da bonificação, direito de subscrição)


class B3Reconciliation(BaseModel):
    ref_date: date | None  # o consolidado mais recente (None = nenhum importado)
    rows: list[ReconRow]


class WalletReconciliation(BaseModel):
    scanned_at: datetime | None  # o scan mais antigo das carteiras escaneadas
    attempt_at: datetime | None  # a última tentativa de scan (o atraso conta daqui)
    stale: bool
    rows: list[ReconRow]


class Reconciliation(BaseModel):
    b3: B3Reconciliation
    wallets: WalletReconciliation
    all_ok: bool


_CRYPTO_QUANTUM = Decimal("1e-8")  # o scan e as operações somam em float: compara a 8 casas


def _dec(v: Any) -> Decimal:
    return Decimal(str(v))


def _crypto(v: Any) -> Decimal:
    return _dec(v).quantize(_CRYPTO_QUANTUM)


async def b3_reconciliation(
    conn: asyncpg.Connection, owner: str, ref_date: date | None = None
) -> B3Reconciliation:
    """Quantidade do app na data do consolidado × a do consolidado, por ativo B3/Tesouro."""
    if ref_date is None:
        ref_date = await conn.fetchval("SELECT max(ref_date) FROM broker_position_snapshots")
    if ref_date is None:
        return B3Reconciliation(ref_date=None, rows=[])
    snap = {
        r["price_ref"]: (r["class"], _dec(r["quantity"]))
        for r in await conn.fetch(
            "SELECT a.price_ref, a.class, s.quantity FROM broker_position_snapshots s "
            "JOIN assets a ON a.id = s.asset_id WHERE s.ref_date = $1 AND a.class = ANY($2)",
            ref_date,
            list(_B3_CLASSES),
        )
    }
    ops: dict[str, list[Any]] = defaultdict(list)
    classes: dict[str, str] = {}
    for r in await conn.fetch(
        "SELECT a.price_ref, a.class, o.tipo, o.quantidade FROM asset_operations o "
        "JOIN assets a ON a.id = o.asset_id WHERE o.user_id = $1 AND o.data_operacao <= $2 "
        "AND a.class = ANY($3)",
        owner,
        ref_date,
        list(_B3_CLASSES),
    ):
        ops[r["price_ref"]].append(r)
        classes[r["price_ref"]] = r["class"]
    rows: list[ReconRow] = []
    for symbol in sorted(set(snap) | set(ops)):
        app = calc.quantity(ops.get(symbol, []))
        origin = snap[symbol][1] if symbol in snap else Decimal(0)
        if app == 0 and origin == 0:
            continue
        cls = snap[symbol][0] if symbol in snap else classes[symbol]
        status = calc.quantity_status(cls, app, origin)
        nota = _explained(symbol, app, origin) if status == "divergente" else None
        rows.append(
            ReconRow(
                symbol=symbol,
                cls=cls,
                app=app,
                origin=origin,
                diff=app - origin,
                status="conferido" if nota else status,
                nota=nota,
            )
        )
    return B3Reconciliation(ref_date=ref_date, rows=rows)


# Direito/recibo de subscrição na B3: 4 letras + 1/2 (ações) ou 12–15 (FIIs) — o app não acompanha
_SUBSCRIPTION = re.compile(r"[A-Z]{4}(1[2-5]|[12])")


def _explained(symbol: str, app: Decimal, origin: Decimal) -> str | None:
    """Diferenças que não são erro (P19): a fração da bonificação, que o consolidado tira até o
    leilão vender (o app a mantém até a venda), e o direito de subscrição, que só o consolidado
    mostra e some no mês seguinte (exercido vira cota; não exercido, expira)."""
    if origin == origin.to_integral_value() and Decimal(0) < app - origin < Decimal(1):
        return "fração da bonificação: o consolidado só mostra ações inteiras até o leilão"
    if app == 0 and origin > 0 and _SUBSCRIPTION.fullmatch(symbol):
        return "direito de subscrição: o app conta quando vira cota"
    return None


async def wallet_rows(conn: asyncpg.Connection, owner: str) -> list[dict[str, Any]]:
    """Escaneado × registrado em operações (`net_quantity`), por ativo cripto, com o valor (a
    leitura da rota v1 /wallets/reconciliation)."""
    scanned = await wallet_service.scanned_quantities(conn, owner)
    ops = await conn.fetch(
        "SELECT asset_symbol, tipo, quantidade FROM asset_operations "
        "WHERE user_id = $1 AND lower(asset_category) = ANY($2::text[])",
        owner,
        [c.lower() for c in CRYPTO_CATEGORIES],
    )
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for op in ops:
        by_symbol[op["asset_symbol"]].append(op)
    registered = {sym: net_quantity(rows) for sym, rows in by_symbol.items()}
    symbols = sorted(set(scanned) | set(registered))
    prices = await wallet_service.prices_by_ticker(conn, symbols)
    out: list[dict[str, Any]] = []
    for sym in symbols:
        s = scanned.get(sym, 0.0)
        reg = registered.get(sym)
        brl, usd = prices.get(sym, (None, None))
        out.append(
            {
                "asset_symbol": sym,
                "scanned_quantity": s,
                "registered_quantity": reg if reg is not None else 0.0,
                "has_registered": reg is not None,
                "delta": s - (reg or 0.0),
                "value_brl": value_of(s, brl),
                "value_usd": value_of(s, usd),
            }
        )
    return out


async def wallet_reconciliation(
    conn: asyncpg.Connection, owner: str, now: datetime | None = None
) -> WalletReconciliation:
    """Cripto não tolera divergência: com operações registradas, a quantidade tem de bater com o
    scan; sem operações, o bloco é o próprio scan (conferido). Scan com mais de 14 h desde a
    última TENTATIVA → desatualizado."""
    rows: list[ReconRow] = []
    for r in await wallet_rows(conn, owner):
        origin = _crypto(r["scanned_quantity"])
        app = _crypto(r["registered_quantity"]) if r["has_registered"] else origin
        rows.append(
            ReconRow(
                symbol=r["asset_symbol"],
                cls="cripto",
                app=app,
                origin=origin,
                diff=app - origin,
                status=calc.quantity_status("cripto", app, origin),
            )
        )
    attempt = await wallet_service.last_scan_attempt(conn)
    now = now or datetime.now(tz=attempt.tzinfo if attempt else None)
    return WalletReconciliation(
        scanned_at=await wallet_service.oldest_scan(conn),
        attempt_at=attempt,
        stale=attempt is not None and now - attempt > SCAN_MAX_AGE,
        rows=rows,
    )


async def reconciliation(conn: asyncpg.Connection, owner: str) -> Reconciliation:
    b3 = await b3_reconciliation(conn, owner)
    wallets = await wallet_reconciliation(conn, owner)
    ok = (
        b3.ref_date is not None
        and all(r.status != "divergente" for r in b3.rows)
        and all(r.status != "divergente" for r in wallets.rows)
        and not wallets.stale
    )
    return Reconciliation(b3=b3, wallets=wallets, all_ok=ok)


async def reconciliation_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """ "{Ativo}: {q} no app, {q'} no consolidado B3." (divergência) e "Carteiras sem scan desde
    {dd/mm/aaaa hh:mm}." (a última tentativa tem mais de 14 h)."""
    out: list[Alert] = []
    b3 = await b3_reconciliation(conn, ctx.owner_id)
    for r in b3.rows:
        if r.status != "divergente":
            continue
        out.append(
            Alert(
                key=f"posicao_divergente:{r.symbol}",
                fingerprint=fingerprint(r.app, r.origin, b3.ref_date),
                severity="divergencia",
                message=f"{r.symbol}: {_qty(r.app)} no app, {_qty(r.origin)} no consolidado B3.",
                action=AlertAction(label="Ver conciliação", route="/investimentos/conciliacao"),
                as_of=b3.ref_date,
            )
        )
    wallets = await wallet_reconciliation(conn, ctx.owner_id)
    if wallets.stale and wallets.attempt_at is not None:
        local = wallets.attempt_at.astimezone(_zone())
        out.append(
            Alert(
                key="carteiras_sem_scan",
                fingerprint=fingerprint(wallets.attempt_at),
                severity="aviso",
                message=f"Carteiras sem scan desde {local:%d/%m/%Y %H:%M}.",
                action=AlertAction(label="Ver conciliação", route="/investimentos/conciliacao"),
                as_of=ctx.today,
            )
        )
    return out


async def close_checks(conn: asyncpg.Connection, month: date) -> list[dict[str, str]]:
    """Precondição do fechamento: posição divergente do consolidado daquele fim de mês pede
    "fechar mesmo assim"."""
    end = month_end(month)
    has = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM broker_position_snapshots WHERE ref_date = $1)", end
    )
    if not has:
        return []
    b3 = await b3_reconciliation(conn, await get_owner_id(conn), end)
    divergent = [r.symbol for r in b3.rows if r.status == "divergente"]
    if not divergent:
        return []
    return [
        {
            "code": "posicao_divergente",
            "kind": "confirma",
            "message": f"{len(divergent)} posição(ões) divergente(s) do consolidado B3 de "
            f"{month_label(month)}: {', '.join(divergent[:5])}.",
        }
    ]


def _qty(v: Decimal | None) -> str:
    if v is None:
        return "—"
    text = f"{v.normalize():f}"
    return text.replace(".", ",")


def _zone() -> ZoneInfo:
    return ZoneInfo(_BRT)
