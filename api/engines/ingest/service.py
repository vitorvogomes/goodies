"""Serviço da engine ingest (AD-5).

Até o protocolo `SourceAdapter` (Story 3.3), os imports v1 (OFX/CSV do Nubank, xlsx da B3)
registram o lote já aplicado por `record_applied_batch`, antes das linhas que gravam — assim toda
linha vinda de arquivo tem `batch_id` desde a Story 2.2.
"""

from __future__ import annotations

import asyncpg

from engines.common.owner import get_owner_id

from . import queries
from .models import BatchFileIn, BatchFileResponse, BatchResponse


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
