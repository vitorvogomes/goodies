"""Story 3.8 — adapters da B3 no protocolo: detecção, período pelo nome (editável), dedup por
operation_hash, regra de cobertura (a mesma operação de movimentação e negociação entra uma vez),
consolidado → broker_position_snapshots, e a página v1."""

from __future__ import annotations

import io
import uuid
from typing import Any

import openpyxl
import pytest

from engines.portfolio.b3_adapter import period_from_name
from tests.ingest.test_protocol import _preview

URL = "/api/v1/ingest"
_NEG = (
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
_MOV = (
    "Entrada/Saída",
    "Data",
    "Movimentação",
    "Produto",
    "Instituição",
    "Quantidade",
    "Preço unitário",
    "Valor da Operação",
)
_POS = ("Produto", "Código de Negociação", "Quantidade", "Preço de Fechamento", "Valor Atualizado")


def _xlsx(sheets: dict[str, list[tuple[Any, ...]]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _confirm(api, headers, body) -> dict[str, Any]:
    r = await api.post(
        f"{URL}/confirm", json={"batch_id": body["batch_id"], "hash": body["hash"]}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _cleanup(pool, tickers: list[str], batches: list[str]) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM broker_position_snapshots s USING asset_aliases a "
            "WHERE a.asset_id = s.asset_id AND a.symbol = ANY($1::text[])",
            tickers,
        )
        await conn.execute(
            "DELETE FROM asset_operations WHERE asset_symbol = ANY($1::text[])", tickers
        )
        await conn.execute("DELETE FROM asset_prices WHERE ticker = ANY($1::text[])", tickers)
        await conn.execute("DELETE FROM import_batches WHERE id = ANY($1::uuid[])", batches)
        await conn.execute(
            "DELETE FROM assets WHERE key = ANY($1::text[])", [f"b3:{t}" for t in tickers]
        )


def test_period_from_name() -> None:
    from datetime import date

    assert period_from_name("movimentacao-2026-06-01_2026-10-16.xlsx", "movimentacao") == (
        date(2026, 6, 1),
        date(2026, 10, 16),
    )
    assert period_from_name("relatorio-consolidado-mensal-2026-marco.xlsx", "consolidado") == (
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert period_from_name("relatorio-consolidado-anual-2025.xlsx", "consolidado") == (
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    assert period_from_name("posicao.xlsx", "consolidado") is None


@pytest.mark.asyncio
async def test_movimentacao_and_negociacao_enter_once(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    t = f"ZB{uuid.uuid4().hex[:2].upper()}3"
    neg = _xlsx(
        {"Negociação": [_NEG, ("05/02/2099", "Compra", "Vista", "-", "X", t, 2, 10.0, 20.0)]}
    )
    mov = _xlsx(
        {
            "Movimentação": [
                _MOV,
                (
                    "Credito",
                    "07/02/2099",
                    "Transferência - Liquidação",
                    f"{t} - EMPRESA",
                    "X",
                    2,
                    10.0,
                    20.0,
                ),
            ]
        }
    )
    batches: list[str] = []
    try:
        body = (
            await _preview(
                api,
                auth_headers,
                [
                    ("negociacao-2099-02-01_2099-02-28.xlsx", neg),
                    ("movimentacao-2099-02-01_2099-02-28.xlsx", mov),
                ],
            )
        ).json()
        batches.append(body["batch_id"])
        n, m = body["files"]
        assert (n["source"], m["source"]) == ("b3_negociacao", "b3_movimentacao")
        assert (n["period_start"], n["period_end"]) == ("2099-02-01", "2099-02-28")
        assert (n["new"], m["new"]) == (1, 1)  # cada um, sozinho, seria novo
        done = await _confirm(api, auth_headers, body)
        assert done["imported"] == 1  # mas no lote entra uma vez só
        again = (
            await _preview(api, auth_headers, [("negociacao-2099-02-01_2099-02-28.xlsx", neg)])
        ).json()
        batches.append(again["batch_id"])
        assert again["files"][0]["new"] == 0
    finally:
        await _cleanup(pool, [t], batches)


@pytest.mark.asyncio
async def test_unnamed_file_needs_period(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    t = f"ZC{uuid.uuid4().hex[:2].upper()}3"
    neg = _xlsx({"Negociação": [_NEG, ("05/03/2099", "Compra", "Vista", "-", "X", t, 1, 5.0, 5.0)]})
    batches: list[str] = []
    try:
        body = (await _preview(api, auth_headers, [("extrato.xlsx", neg)])).json()
        batches.append(body["batch_id"])
        f = body["files"][0]
        assert f["needs"] == ["period"] and f["period_start"] is None
        blocked = await api.post(
            f"{URL}/confirm",
            json={"batch_id": body["batch_id"], "hash": body["hash"]},
            headers=auth_headers,
        )
        assert blocked.status_code == 422
        re = (
            await api.post(
                f"{URL}/replan",
                json={
                    "batch_id": body["batch_id"],
                    "overrides": {
                        f["file_hash"]: {"period_start": "2099-03-01", "period_end": "2099-03-31"}
                    },
                },
                headers=auth_headers,
            )
        ).json()
        batches.append(re["batch_id"])
        assert re["files"][0]["needs"] == []
        await _confirm(api, auth_headers, re)
        async with pool.acquire() as conn:
            period = await conn.fetchrow(
                "SELECT period_start::text, period_end::text FROM import_batch_files "
                "WHERE batch_id = $1::uuid",
                re["batch_id"],
            )
        assert tuple(period) == ("2099-03-01", "2099-03-31")
    finally:
        await _cleanup(pool, [t], batches)


@pytest.mark.asyncio
async def test_consolidado_writes_snapshots(api, auth_headers, pool) -> None:
    import main  # noqa: F401

    t = f"ZD{uuid.uuid4().hex[:2].upper()}3"
    pos = _xlsx({"Posição - Ações": [_POS, (f"{t} - EMPRESA", t, 7, 10.0, 70.0)]})
    batches: list[str] = []
    try:
        body = (
            await _preview(api, auth_headers, [("relatorio-consolidado-anual-2099.xlsx", pos)])
        ).json()
        batches.append(body["batch_id"])
        f = body["files"][0]
        assert (f["source"], f["period_end"], f["new"]) == ("b3_consolidado", "2099-12-31", 1)
        await _confirm(api, auth_headers, body)
        async with pool.acquire() as conn:
            snap = await conn.fetchrow(
                "SELECT s.ref_date::text, a.key, s.quantity, s.reported_value, s.batch_id::text "
                "FROM broker_position_snapshots s JOIN assets a ON a.id = s.asset_id "
                "WHERE a.key = $1",
                f"b3:{t}",
            )
        assert (snap["ref_date"], snap["quantity"], float(snap["reported_value"])) == (
            "2099-12-31",
            7,
            70.0,
        )
        assert snap["batch_id"] == body["batch_id"]
        again = (
            await _preview(api, auth_headers, [("relatorio-consolidado-anual-2099.xlsx", pos)])
        ).json()
        batches.append(again["batch_id"])
        assert (again["files"][0]["new"], again["files"][0]["existing"]) == (0, 1)
    finally:
        await _cleanup(pool, [t], batches)
