"""Story 3.9 — Bloco Fontes e avisos de fonte: atualizado até derivado de `import_batch_files`
(applied/legacy), limites do FR-3 e lacunas (Nubank por intervalo; consolidado por mês)."""

from __future__ import annotations

from datetime import date

from engines.ingest.calc import Coverage, consolidado_gaps, interval_gaps, is_stale, required_until


def test_required_until_follows_day_15() -> None:
    assert required_until(date(2026, 10, 16)) == date(2026, 9, 30)
    assert required_until(date(2026, 10, 15)) == date(2026, 8, 31)


def test_staleness_limits() -> None:
    today = date(2026, 10, 18)
    assert is_stale("nubank_pf", date(2026, 10, 10), today) is True  # 8 dias
    assert is_stale("nubank_pf", date(2026, 10, 11), today) is False
    assert is_stale("nubank_mei", date(2026, 9, 30), today) is False
    assert is_stale("nubank_mei", date(2026, 9, 29), today) is True
    assert is_stale("b3_consolidado", date(2026, 8, 31), today) is True
    assert is_stale("b3_movimentacao", date(2025, 1, 1), today) is False  # sem limite
    assert is_stale("nubank_pf", None, today) is False  # nunca importado: sem aviso de atraso


def test_interval_gaps_ignore_contiguous_and_legacy_inside() -> None:
    cov = [
        Coverage(date(2024, 6, 1), date(2026, 5, 31)),  # legacy
        Coverage(date(2026, 6, 1), date(2026, 6, 30)),
        Coverage(date(2026, 8, 1), date(2026, 8, 31)),
        Coverage(date(2026, 8, 10), date(2026, 9, 15)),
    ]
    assert interval_gaps(cov) == [(date(2026, 7, 1), date(2026, 7, 31))]


def test_consolidado_gaps_by_month() -> None:
    cov = [
        Coverage(date(2025, 1, 1), date(2025, 12, 31)),  # anual
        Coverage(date(2026, 1, 1), date(2026, 1, 31)),
        Coverage(date(2026, 3, 1), date(2026, 3, 31)),
    ]
    assert consolidado_gaps(cov) == [(date(2026, 2, 1), date(2026, 2, 28))]


async def test_sources_endpoint_and_alerts(api, auth_headers, ofx_account, pool) -> None:
    import main  # noqa: F401
    from engines.alerts import service as alerts_service

    r = await api.get("/api/v1/ingest/sources", headers=auth_headers)
    assert r.status_code == 200
    keys = [s["key"] for s in r.json()]
    assert keys == ["nubank_pf", "nubank_mei", "b3_movimentacao", "b3_consolidado"]
    first = r.json()[0]
    assert first["label"] == "Nubank PF" and first["kind"] == "OFX ou CSV"
    async with pool.acquire() as conn:
        alerts = await alerts_service.active_alerts(conn)
    assert all(not a.key.startswith("fonte_desatualizada:b3_movimentacao") for a in alerts.items)
