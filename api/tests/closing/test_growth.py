"""Story 9.2 — crescimento do patrimônio = aporte + resultado, rentabilidade por classe e ativo e o
ativo de melhor desempenho; antes do primeiro mês coberto → indisponível com o motivo."""

from __future__ import annotations

from decimal import Decimal

import pytest

from engines.common.dates import today_brt

D = Decimal
URL = "/api/v1/closing/growth"


@pytest.mark.asyncio
async def test_growth_identity_and_best(api, auth_headers) -> None:
    import main  # noqa: F401

    mes = f"{today_brt():%Y-%m}"
    body = (await api.get(f"{URL}?periodo={mes}&leitura=mes", headers=auth_headers)).json()
    assert body["available"] is True and body["reason"] is None
    crescimento, aporte, resultado = (
        D(str(body[k])) for k in ("crescimento", "aporte", "resultado")
    )
    assert crescimento == aporte + resultado
    assert D(str(body["end_value"])) - D(str(body["start_value"])) == crescimento
    rates = [a["xirr_mensal"] for a in body["assets"]]
    assert rates == sorted(rates, reverse=True)  # do melhor para o pior
    if rates:
        assert body["best"]["xirr_mensal"] == rates[0]


@pytest.mark.asyncio
async def test_before_first_month_is_unavailable(api, auth_headers) -> None:
    r = (await api.get(f"{URL}?periodo=2024-07&leitura=mes", headers=auth_headers)).json()
    assert (r["available"], r["reason"]) == (False, "antes_do_primeiro_fechamento")
    assert r["crescimento"] is None and r["aporte"] is None
    since = (
        await api.get(f"{URL}?periodo={today_brt():%Y-%m}&leitura=inicio", headers=auth_headers)
    ).json()
    assert since["available"] is True and since["start_value"] == 0.0
