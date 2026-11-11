"""v2.2 — histórico de preço para a oportunidade: o COTAHIST da B3 (layout fixo), o CSV do
Tesouro com todas as datas e o CoinGecko; grava só os dias que faltam."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest

from engines.common.dates import today_brt
from engines.market import history_backfill as hb


def _cotahist(ticker: str, day: date, close_cents: int, tpmerc: str = "010") -> str:
    line = (
        "01"
        + f"{day:%Y%m%d}"
        + "02"
        + ticker.ljust(12)
        + tpmerc
        + "PETROBRAS".ljust(12)
        + "PN".ljust(10)
        + " " * 3
        + "R$".ljust(4)
        + "0" * 13 * 4
        + f"{close_cents:013d}"
    )
    return line.ljust(245)


def test_parse_cotahist_line_reads_close_of_spot_market() -> None:
    line = _cotahist("PETR4", date(2026, 5, 4), 3812)
    assert hb.parse_cotahist_line(line, {"PETR4"}) == (
        "PETR4",
        (date(2026, 5, 4), Decimal("38.12")),
    )
    assert hb.parse_cotahist_line(line, {"VALE3"}) is None  # fora da carteira
    assert hb.parse_cotahist_line(_cotahist("PETR4", date(2026, 5, 4), 1, "070"), {"PETR4"}) is None
    assert hb.parse_cotahist_line("00COTAHIST.2026BOVESPA", {"PETR4"}) is None


@pytest.mark.asyncio
async def test_b3_history_from_zip_and_write_only_missing(pool: Any) -> None:
    day = today_brt() - timedelta(days=3)
    old = today_brt() - timedelta(days=900)
    body = "\n".join(
        [
            "00COTAHIST.2026BOVESPA 20260101",
            _cotahist("ZZBK3", day, 1050),
            _cotahist("ZZBK3", old, 999),  # antes do `since`: fora
        ]
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("COTAHIST_A.TXT", body.encode("latin-1"))
    payload = buf.getvalue()

    def handler(req: httpx.Request) -> httpx.Response:
        if str(today_brt().year) in req.url.path:
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await hb.b3_history(["ZZBK3"], today_brt() - timedelta(days=30), client)
    assert found["ZZBK3"] == [(day, Decimal("10.50"))]
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO asset_price_history (ticker, ref_date, price_brl, source, is_manual) "
                "VALUES ('ZZBK3', $1, 11, 'brapi', false)",
                day - timedelta(days=1),
            )
            n = await hb.write_missing(
                conn,
                "ZZBK3",
                [(day - timedelta(days=1), Decimal(1)), (day, Decimal("10.50"))],
                "b3_cotahist",
            )
            kept = await conn.fetchval(
                "SELECT price_brl FROM asset_price_history "
                "WHERE ticker = 'ZZBK3' AND ref_date = $1",
                day - timedelta(days=1),
            )
        finally:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = 'ZZBK3'")
    assert n == 1 and kept == 11  # o dia que já existia não muda


@pytest.mark.asyncio
async def test_source_failure_is_soft() -> None:
    def boom(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as client:
        assert await hb.b3_history(["PETR4"], today_brt(), client) == {}
        assert await hb.treasury_history(["Tesouro IPCA+ 2040"], today_brt(), client) == {}
        assert await hb.crypto_history({"BTC": "bitcoin"}, client, pause=0) == {}


@pytest.mark.asyncio
async def test_run_writes_by_source_and_only_missing_days(pool: Any) -> None:
    """A rodada lê os ativos, baixa sem segurar conexão e grava só o que falta, com as contagens
    por fonte (os stats do job em Ajustes › Atualização)."""
    day = today_brt() - timedelta(days=2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("C.TXT", _cotahist("ZZRN3", day, 777).encode("latin-1"))
    payload = buf.getvalue()

    def handler(req: httpx.Request) -> httpx.Response:
        if "COTAHIST" in req.url.path and str(today_brt().year) in req.url.path:
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO assets (key, class, name, price_ref, valuation) "
            "VALUES ('b3:ZZRN3', 'acoes_br', 'ZZRN3', 'ZZRN3', 'mercado')"
        )
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            stats = await hb.run(pool, client=client)
            again = await hb.run(pool, client=client)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM asset_price_history WHERE ticker = 'ZZRN3'")
            await conn.execute("DELETE FROM assets WHERE key = 'b3:ZZRN3'")
    assert stats["b3"]["days_written"] >= 1
    assert again["b3"]["days_written"] == 0  # nada novo: não sobrescreve
