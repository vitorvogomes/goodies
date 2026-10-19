"""Review final — o cache do histórico de sugestões acompanha a descrição editada e a categoria
arquivada (antes a versão só olhava a contagem de confirmadas e o último evento)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from engines.ledger.importer import suggestion_history, tokens


@pytest.mark.asyncio
async def test_history_follows_description_edit_and_archived_category(pool: Any) -> None:
    word, other = f"zq{uuid.uuid4().hex[:8]}", f"zw{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        cat = await conn.fetchrow(
            "SELECT c.id FROM categories c JOIN category_groups g ON g.id = c.group_id "
            "WHERE c.role = 'consumo' AND NOT g.is_system AND c.is_active LIMIT 1"
        )
        acc = await conn.fetchval(
            "INSERT INTO accounts (name, type) VALUES ($1, 'bank') RETURNING id",
            f"sug-{uuid.uuid4().hex[:6]}",
        )
        tx = await conn.fetchval(
            "INSERT INTO transactions (account_id, date, amount, category_id, kind, description, "
            "review_status) VALUES ($1, '2099-01-05', -10, $2, 'expense', $3, 'confirmed') "
            "RETURNING id",
            acc,
            cat["id"],
            f"Compra {word}",
        )
        try:
            first = await suggestion_history(conn)
            assert any(i.tokens == tokens(f"Compra {word}") for i in first)
            await conn.execute(
                "UPDATE transactions SET description = $2 WHERE id = $1", tx, f"Compra {other}"
            )
            edited = await suggestion_history(conn)
            assert any(i.tokens == tokens(f"Compra {other}") for i in edited)
            assert not any(i.tokens == tokens(f"Compra {word}") for i in edited)
            await conn.execute("UPDATE categories SET is_active = false WHERE id = $1", cat["id"])
            archived = await suggestion_history(conn)
            assert not any(i.category_id == str(cat["id"]) for i in archived)
        finally:
            await conn.execute("UPDATE categories SET is_active = true WHERE id = $1", cat["id"])
            await conn.execute("DELETE FROM transactions WHERE id = $1", tx)
            await conn.execute("DELETE FROM accounts WHERE id = $1", acc)
