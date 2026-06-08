"""D — sugestão híbrida de categoria (função pura + endpoint DB-backed)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import pytest

from engines.ledger.suggest import suggest_category

_INSERT_TX = (
    "INSERT INTO transactions (account_id, date, amount, category, kind, "
    "description, external_id) VALUES ($1::uuid, $2, $3, $4, 'expense', $5, $6)"
)

_HIST = [
    ("Uber * trip helpful guy", "Transporte"),
    ("Uber * trip downtown ride", "Transporte"),
    ("Mercado Pao de Acucar loja 12", "Alimentação"),
    ("iFood pedido restaurante", "Comida Fora"),
]


def test_suggests_most_similar_category() -> None:
    res = suggest_category("Uber * trip airport ride", _HIST)
    assert res is not None
    assert res[0] == "Transporte"
    assert res[1] >= 0.6


def test_returns_none_when_no_good_match() -> None:
    assert suggest_category("Posto Ipiranga 9988 gasolina", _HIST) is None


def test_empty_history_returns_none() -> None:
    assert suggest_category("qualquer descrição", []) is None


def test_empty_description_returns_none() -> None:
    assert suggest_category("", _HIST) is None


def test_threshold_filters_weak_match() -> None:
    assert suggest_category("xyzk", [("abcd", "Cat")]) is None
    # baixando o threshold, o melhor (único) candidato passa
    res = suggest_category("xyzk", [("abcd", "Cat")], threshold=0.0)
    assert res is not None and res[0] == "Cat"


@pytest.mark.asyncio
async def test_suggestions_endpoint(
    api: Any, auth_headers: dict, account: str, pool: Any
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_TX, account, datetime.date(2026, 1, 1), Decimal("-30"),
            "Transporte", "PAGAMENTO PIX UBER DO BRASIL TECNOLOGIA", "sug-h1",
        )
        await conn.execute(
            _INSERT_TX, account, datetime.date(2026, 2, 1), Decimal("-25"),
            "outros", "PAGAMENTO PIX UBER DO BRASIL TECNOLOGIA LTDA", "sug-p1",
        )
    resp = await api.get("/api/v1/transactions/suggestions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert any(
        s["suggested_category"] == "Transporte"
        and s["description"] == "PAGAMENTO PIX UBER DO BRASIL TECNOLOGIA LTDA"
        for s in body
    )
