"""Serviço da engine ingest (AD-5).

O app importa pelo protocolo `SourceAdapter` (prévia `staged` → confirmação, Story 3.3). Scripts e o
import B3 v1 ainda registram o lote já aplicado por `record_applied_batch`, antes das linhas que
gravam — toda linha vinda de arquivo tem `batch_id` desde a Story 2.2.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import asyncpg

from engines.common.alerts import Alert, AlertAction, AlertContext, fingerprint
from engines.common.cache import invalidate_xirr_cache
from engines.common.month_status import month_status
from engines.common.owner import get_owner_id

from . import queries
from .models import (
    BatchFileIn,
    BatchFileResponse,
    BatchResponse,
    ConfirmOut,
    FilePlanOut,
    PreviewOut,
)
from .protocol import FilePlan, ParsedFile, PlanError, SourceAdapter


async def record_applied_batch(conn: asyncpg.Connection, files: list[BatchFileIn]) -> str:
    """Cria um lote `applied` com os arquivos informados e devolve o `batch_id`."""
    if not files:
        raise ValueError("lote sem arquivos")
    owner = await get_owner_id(conn)
    batch_id = await queries.insert_batch(conn, owner, "applied")
    for f in files:
        await queries.insert_file(conn, batch_id, owner, f.model_dump())
    return batch_id


async def list_batches(conn: asyncpg.Connection, limit: int = 20) -> list[BatchResponse]:
    """Lotes mais recentes primeiro, com os arquivos de cada um (leitura pública da dona)."""
    owner = await get_owner_id(conn)
    batches = await queries.select_batches(conn, owner, limit)
    files = await queries.select_files(conn, [str(b["id"]) for b in batches])
    by_batch: dict[str, list[BatchFileResponse]] = {}
    for f in files:
        item = BatchFileResponse(
            id=str(f["id"]),
            batch_id=str(f["batch_id"]),
            source=f["source"],
            account_id=str(f["account_id"]) if f["account_id"] else None,
            broker=f["broker"],
            file_name=f["file_name"],
            file_hash=f["file_hash"],
            period_start=f["period_start"],
            period_end=f["period_end"],
            reported_balance=f["reported_balance"],
            reported_balance_date=f["reported_balance_date"],
        )
        by_batch.setdefault(item.batch_id, []).append(item)
    return [
        BatchResponse(
            id=str(b["id"]),
            status=b["status"],
            created_at=b["created_at"],
            applied_at=b["applied_at"],
            files=by_batch.get(str(b["id"]), []),
        )
        for b in batches
    ]


# --------------------------------------------------------------------------------------------
# Protocolo SourceAdapter: prévia → confirmação (AD-5 — Story 3.3)
# --------------------------------------------------------------------------------------------

UNKNOWN_FORMAT = (
    "Formato não reconhecido. Aceitos: OFX Nubank, CSV Nubank, B3 movimentação, negociação e "
    "consolidado (.xlsx)."
)
_adapters: list[SourceAdapter] = []
BatchHook = Callable[[asyncpg.Connection, str], Awaitable[None]]
_on_applied: list[BatchHook] = []
_on_undo: list[BatchHook] = []


def register_adapter(adapter: SourceAdapter) -> None:
    if adapter not in _adapters:
        _adapters.append(adapter)


def registered_sources() -> list[str]:
    return [s for a in _adapters for s in a.sources]


def register_on_batch_applied(hook: BatchHook) -> None:
    """Derivações de engines de cima (portfolio), na mesma transação do `apply` (AD-5/AD-6)."""
    if hook not in _on_applied:
        _on_applied.append(hook)


def register_on_batch_undo(hook: BatchHook) -> None:
    if hook not in _on_undo:
        _on_undo.append(hook)


class BatchError(Exception):
    """Confirmação recusada; `code` vira o `error` do contrato HTTP."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _adapter_for(source: str) -> SourceAdapter:
    return next(a for a in _adapters if source in a.sources)


async def _plan_files(
    conn: asyncpg.Connection,
    files: list[tuple[str, bytes]],
    overrides: dict[str, dict[str, str]],
) -> list[FilePlan]:
    plans: list[FilePlan] = []
    for name, content in files:
        digest = hashlib.sha256(content).hexdigest()
        detected = next(
            ((a, s) for a in _adapters if (s := a.detect(name, content)) is not None), None
        )
        if detected is None:
            plans.append(FilePlan(None, name, digest, error=UNKNOWN_FORMAT))
            continue
        adapter, source = detected
        mine = overrides.get(digest, {})
        try:
            parsed = ParsedFile(source, name, digest, content, adapter.parse(source, name, content))
            plan = await adapter.plan(conn, parsed, mine)
        except PlanError as exc:
            plan = FilePlan(source, name, digest, error=str(exc))
        plan.overrides = mine
        plans.append(plan)
    applied = {
        r["file_hash"]
        for r in await conn.fetch(queries.APPLIED_HASHES, [p.file_hash for p in plans])
    }
    for p in plans:
        p.already_imported = p.file_hash in applied
    return plans


def _plan_hash(plans: list[FilePlan]) -> str:
    raw = json.dumps([p.summary() for p in plans], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _out(p: FilePlan) -> FilePlanOut:
    return FilePlanOut(
        source=p.source,
        file_name=p.file_name,
        file_hash=p.file_hash,
        account_id=p.account_id,
        account_name=p.account_name,
        broker=p.broker,
        period_start=p.period_start,
        period_end=p.period_end,
        new=p.new,
        existing=p.existing,
        skipped=p.skipped,
        reported_balance=p.reported_balance,
        reported_balance_date=p.reported_balance_date,
        already_imported=p.already_imported,
        needs=p.needs,
        warnings=p.warnings,
        error=p.error,
        detail=p.detail,
    )


async def preview(
    conn: asyncpg.Connection,
    files: list[tuple[str, bytes]],
    overrides: dict[str, dict[str, str]] | None = None,
) -> PreviewOut:
    """Planeja os arquivos e guarda um lote `staged` (plano + hash, 24 h). Não grava fato."""
    overrides = overrides or {}
    await conn.execute(queries.DROP_EXPIRED)
    plans = await _plan_files(conn, files, overrides)
    digest = _plan_hash(plans)
    stored = {
        "files": [{"name": n, "content": base64.b64encode(c).decode()} for n, c in files],
        "overrides": overrides,
        "summary": [_out(p).model_dump(mode="json") for p in plans],
    }
    row = await conn.fetchrow(
        queries.INSERT_STAGED, await get_owner_id(conn), json.dumps(stored), digest
    )
    return PreviewOut(
        batch_id=str(row["id"]),
        hash=digest,
        expires_at=row["expires_at"],
        files=[_out(p) for p in plans],
        new=sum(p.new for p in plans if p.error is None),
    )


def _stored_files(plan: Any) -> tuple[list[tuple[str, bytes]], dict[str, dict[str, str]]]:
    data = json.loads(plan) if isinstance(plan, str) else plan
    files = [(f["name"], base64.b64decode(f["content"])) for f in data["files"]]
    return files, data.get("overrides", {})


async def replan(
    conn: asyncpg.Connection, batch_id: str, overrides: dict[str, dict[str, str]]
) -> PreviewOut:
    """Escolha na linha da prévia (conta do CSV, período B3): novo `staged` com novo hash."""
    row = await conn.fetchrow(queries.STAGED_FOR_UPDATE, batch_id)
    if row is None or row["status"] != "staged":
        raise BatchError("lote_inexistente", "Prévia não encontrada. Envie os arquivos de novo.")
    files, previous = _stored_files(row["plan"])
    merged = {**previous}
    for file_hash, chosen in overrides.items():
        merged[file_hash] = {**merged.get(file_hash, {}), **chosen}
    return await preview(conn, files, merged)


async def confirm(conn: asyncpg.Connection, batch_id: str, plan_hash: str) -> ConfirmOut:
    """Re-planeja, exige o mesmo hash e roda todos os `apply` numa transação só."""
    async with conn.transaction():
        row = await conn.fetchrow(queries.STAGED_FOR_UPDATE, batch_id)
        if row is None:
            raise BatchError("lote_inexistente", "Prévia não encontrada.", 404)
        if row["status"] != "staged":
            raise BatchError("lote_ja_aplicado", "Esse lote já foi importado.")
        if row["expired"]:
            raise BatchError("previa_expirada", "A prévia expirou. Envie os arquivos de novo.")
        files, overrides = _stored_files(row["plan"])
        plans = await _plan_files(conn, files, overrides)
        if plan_hash != row["plan_hash"] or _plan_hash(plans) != plan_hash:
            raise BatchError(
                "previa_desatualizada", "A base mudou desde a prévia. Veja a prévia de novo."
            )
        if any(p.needs for p in plans if p.error is None):
            raise BatchError("escolha_pendente", "Escolha a conta dos arquivos marcados.", 422)
        owner = await get_owner_id(conn)
        months: set[date] = set()
        imported = 0
        details: list[dict[str, Any]] = []
        ready = [p for p in plans if p.error is None and p.source is not None]
        ready.sort(
            key=lambda p: (
                _adapter_for(str(p.source)).apply_rank(str(p.source)),
                p.period_end or date.min,
            )
        )
        for p in ready:
            assert p.source is not None
            applied = await _adapter_for(p.source).apply(conn, p, batch_id)
            imported += applied.inserted
            months |= applied.months
            details.append(applied.detail)
            await queries.insert_file(
                conn,
                batch_id,
                owner,
                {
                    "source": p.source,
                    "account_id": p.account_id,
                    "broker": p.broker,
                    "file_name": p.file_name,
                    "file_hash": p.file_hash,
                    "period_start": p.period_start,
                    "period_end": p.period_end,
                    "reported_balance": p.reported_balance,
                    "reported_balance_date": p.reported_balance_date,
                },
            )
        await conn.execute(queries.MARK_APPLIED, batch_id)
        for hook in _on_applied:
            await hook(conn, batch_id)
        port = month_status()
        for month in sorted(months):
            await port.mark_dirty(conn, month)
    await invalidate_xirr_cache(owner)  # AD-5: toda escrita de lote invalida o XIRR
    return ConfirmOut(
        batch_id=batch_id, imported=imported, files=[_out(p) for p in plans], applied=details
    )


async def already_imported_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider (AD-10): prévia recente de arquivo já importado e sem nada novo."""
    alerts: dict[str, Alert] = {}
    for row in await conn.fetch(queries.RECENT_STAGED):
        data = json.loads(row["plan"]) if isinstance(row["plan"], str) else row["plan"]
        for f in data.get("summary", []):
            if f["already_imported"] and f["new"] == 0 and f["error"] is None:
                alerts.setdefault(
                    f["file_hash"],
                    Alert(
                        key=f"arquivo_ja_importado:{f['file_hash']}",
                        fingerprint=fingerprint(f["file_hash"]),
                        severity="aviso",
                        message=f"Arquivo já importado: {f['file_name']}. 0 transações novas.",
                        action=AlertAction(
                            label="Importar", route="/visao-geral/painel", params={"importar": "1"}
                        ),
                        as_of=ctx.today,
                    ),
                )
    return list(alerts.values())


async def csv_unconfirmed_alerts(conn: asyncpg.Connection, ctx: AlertContext) -> list[Alert]:
    """Provider (Story 3.7): conta cujo último extrato aplicado é CSV, sem OFX que cubra o mesmo
    período — o CSV não traz saldo, então não há conferência."""
    return [
        Alert(
            key=f"csv_sem_conferencia:{r['account_id']}",
            fingerprint=fingerprint(r["file_hash"]),
            severity="aviso",
            message="CSV importado sem conferência de saldo. Só o OFX permite conferir.",
            action=AlertAction(
                label="Importar OFX", route="/visao-geral/painel", params={"importar": "1"}
            ),
            as_of=r["period_end"],
        )
        for r in await conn.fetch(queries.CSV_WITHOUT_OFX)
    ]
