"""A4 — POST /api/v1/portfolio/import-b3 (octet-stream + dry-run)."""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

_NEG_HEADER = (
    "Data do Negócio",
    "Tipo de Movimentação",
    "Mercado",
    "Prazo/Vencimento",
    "Instituição",
    "Código de Negociação",
    "Quantidade",
    "Preço",
    "Valor",
)
_OCTET = "application/octet-stream"


def _xlsx(sheets: dict[str, list[tuple[Any, ...]]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _neg_xlsx(rows: list[tuple[Any, ...]]) -> bytes:
    return _xlsx({"Negociação": [_NEG_HEADER, *rows]})


async def _count_ops(pool: Any, symbol: str) -> int:
    # Desde a Story 3.8 o import passa pelo protocolo: a operação é do dono (AD-18), então o teste
    # conta pelo ticker (único por teste).
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM asset_operations WHERE asset_symbol = $1", symbol
        )


class TestImportB3Endpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api: AsyncClient) -> None:
        resp = await api.post("/api/v1/portfolio/import-b3", content=b"x")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_garbage_is_422(self, api: AsyncClient, portfolio_user: dict) -> None:
        resp = await api.post(
            "/api/v1/portfolio/import-b3",
            content=b"definitely not an xlsx",
            headers={**portfolio_user["headers"], "Content-Type": _OCTET},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_is_422(self, api: AsyncClient, portfolio_user: dict) -> None:
        resp = await api.post(
            "/api/v1/portfolio/import-b3",
            content=b"",
            headers=portfolio_user["headers"],
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_dry_run_then_confirm_then_idempotent(
        self, api: AsyncClient, pool: Any, portfolio_user: dict
    ) -> None:
        headers = portfolio_user["headers"]
        sym = f"Q{uuid.uuid4().hex[:3].upper()}3"
        data = _neg_xlsx(
            [("05/06/2026", "Compra", "Frac", "-", "SANT", f"{sym}F", 3, 19.46, 58.38)]
        )
        h = {**headers, "Content-Type": _OCTET}
        try:
            # dry-run: prevê, não grava
            r = await api.post(
                "/api/v1/portfolio/import-b3?dry_run=true&filename=x.xlsx", content=data, headers=h
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["file_type"] == "negociacao"
            assert body["imported"] == 1
            assert body["dry_run"] is True
            assert await _count_ops(pool, sym) == 0

            # confirm: grava
            r2 = await api.post(
                "/api/v1/portfolio/import-b3?dry_run=false", content=data, headers=h
            )
            assert r2.json()["imported"] == 1
            assert await _count_ops(pool, sym) == 1

            # idempotente: re-import não duplica
            r3 = await api.post("/api/v1/portfolio/import-b3", content=data, headers=h)
            assert r3.json()["imported"] == 0
            assert r3.json()["skipped_duplicate"] == 1
            assert await _count_ops(pool, sym) == 1
        finally:
            async with pool.acquire() as conn:
                batches = [
                    r["batch_id"]
                    for r in await conn.fetch(
                        "SELECT DISTINCT batch_id FROM asset_operations WHERE asset_symbol = $1",
                        sym,
                    )
                ]
                await conn.execute("DELETE FROM asset_operations WHERE asset_symbol = $1", sym)
                await conn.execute("DELETE FROM import_batches WHERE id = ANY($1::uuid[])", batches)
