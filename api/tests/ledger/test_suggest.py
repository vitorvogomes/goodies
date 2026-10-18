"""D — sugestão híbrida de categoria (função pura + endpoint DB-backed)."""

from __future__ import annotations

from engines.ledger.suggest import suggest_category

_INSERT_TX = (
    "INSERT INTO transactions (account_id, date, amount, category_id, kind, description, "
    "external_id) VALUES ($1::uuid, $2, $3, (SELECT id FROM categories WHERE name = $4), "
    "'expense', $5, $6)"
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
