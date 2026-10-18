"""Story 3.6 — sugestão para toda transação nova sem regra: a confirmada mais parecida (Jaccard dos
tokens normalizados ≥ 0,6; empate → a mais recente), de qualquer tipo, com o mesmo sinal."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

import pytest

from engines.ledger.importer import StatementEntry, import_statement
from engines.ledger.suggest import HistoryItem, best_suggestion, jaccard, tokens


def _h(desc: str, cat: str, positive: bool = False) -> HistoryItem:
    return HistoryItem(tokens(desc), cat, positive)


def test_tokens_normalize_case_accents_and_numbers() -> None:
    assert tokens("Pagamento PIX — Padaria São João 1234") == frozenset(
        {"pagamento", "pix", "padaria", "sao", "joao"}
    )
    assert jaccard(tokens("a b c"), tokens("a b d")) == pytest.approx(0.5)


# (descrição nova, valor, histórico, categoria esperada ou None)
CASES: list[tuple[str, str, list[HistoryItem], str | None]] = [
    # gasto
    (
        "UBER *TRIP 1234 SAO PAULO",
        "-20",
        [_h("UBER *TRIP 9876 SAO PAULO", "transporte")],
        "transporte",
    ),
    # receita (trabalho)
    (
        "Transferência recebida pelo Pix - ACME LTDA",
        "5000",
        [_h("Transferência recebida pelo Pix - ACME LTDA", "trabalho", True)],
        "trabalho",
    ),
    # investimento
    (
        "Aplicação RDB caixinha Viagem",
        "-300",
        [_h("Aplicação RDB caixinha Viagem", "invest")],
        "invest",
    ),
    # transferência
    (
        "Transferência enviada pelo Pix - Fulano de Tal",
        "-50",
        [_h("Transferência enviada pelo Pix - Fulano de Tal", "transfer")],
        "transfer",
    ),
    # negativos: sem histórico, abaixo de 0,6, sinal trocado
    ("Padaria do Zé", "-8", [], None),
    ("Posto Ipiranga gasolina", "-200", [_h("UBER *TRIP SAO PAULO", "transporte")], None),
    (
        "Transferência recebida pelo Pix - ACME LTDA",
        "-10",
        [_h("Transferência recebida pelo Pix - ACME LTDA", "trabalho", True)],
        None,
    ),
]


@pytest.mark.parametrize(("desc", "amount", "history", "expected"), CASES)
def test_cases(desc: str, amount: str, history: list[HistoryItem], expected: str | None) -> None:
    got = best_suggestion(desc, Decimal(amount), history)
    assert (got.category_id if got else None) == expected


def test_tie_goes_to_most_recent() -> None:
    history = [_h("Mercado Bom Preço", "nova"), _h("Mercado Bom Preço", "velha")]  # recente 1º
    got = best_suggestion("Mercado Bom Preço", Decimal("-1"), history)
    assert got is not None and got.category_id == "nova" and got.score == 1.0


@pytest.mark.asyncio
async def test_import_suggests_from_confirmed_history(pool: Any) -> None:
    async with pool.acquire() as conn:
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
            f"sug-{uuid.uuid4().hex[:6]}",
        )
        word = f"zq{uuid.uuid4().hex[:6]}"
        target = await conn.fetchval(
            "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE c.role = 'consumo' AND NOT g.is_system ORDER BY c.key LIMIT 1"
        )
        try:
            await conn.execute(
                "INSERT INTO transactions (account_id, date, amount, category, category_id, kind, "
                "description, external_id, category_source, review_status) "
                "VALUES ($1, '2099-01-01', -10, 'x', $2, 'expense', $3, $4, 'manual', 'confirmed')",
                acc,
                target,
                f"Loja {word} centro",
                uuid.uuid4().hex,
            )
            entries = [
                StatementEntry(
                    uuid.uuid4().hex,
                    datetime.date(2099, 2, 1),
                    Decimal("-12"),
                    f"Loja {word} centro 0042",
                ),
                StatementEntry(
                    uuid.uuid4().hex,
                    datetime.date(2099, 2, 2),
                    Decimal("-7"),
                    f"Coisa {uuid.uuid4().hex[:8]} inédita",
                ),
            ]
            await import_statement(conn, acc, entries)
            rows = {
                r["description"]: r
                for r in await conn.fetch(
                    "SELECT t.description, t.category_id, t.category_source, t.review_status, "
                    "c.key FROM transactions t JOIN categories c ON c.id = t.category_id "
                    "WHERE t.account_id = $1 AND t.date >= '2099-02-01'",
                    acc,
                )
            }
            hit = rows[entries[0].description]
            assert (hit["category_id"], hit["category_source"], hit["review_status"]) == (
                target,
                "suggestion",
                "pending",
            )
            miss = rows[entries[1].description]
            assert miss["key"] == "sistema:saida_a_classificar"
        finally:
            await conn.execute("DELETE FROM transactions WHERE account_id = $1", acc)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
