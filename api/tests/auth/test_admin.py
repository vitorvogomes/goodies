"""Upsert do admin (`seed_admin` e bootstrap — ADR-018): trocar a senha encerra as sessões."""

from __future__ import annotations

from typing import Any

import pytest

from auth.admin import upsert_admin
from auth.security import verify_password
from scripts.ops import seed_admin
from tests.conftest import TEST_DSN


@pytest.mark.asyncio
async def test_password_change_revokes_refresh_token(pool: Any) -> None:
    email = "rotacao@goodies.test"
    await upsert_admin(TEST_DSN, email, "senha-antiga-" + "a" * 20)
    await pool.execute(
        "UPDATE users SET refresh_token_hash = 'sessao-viva' WHERE email = $1", email
    )
    await upsert_admin(TEST_DSN, email, "senha-nova-" + "b" * 20)
    row = await pool.fetchrow(
        "SELECT password_hash, refresh_token_hash FROM users WHERE email = $1", email
    )
    assert verify_password("senha-nova-" + "b" * 20, row["password_hash"])
    assert row["refresh_token_hash"] is None
    await pool.execute("DELETE FROM users WHERE email = $1", email)


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["", "   "])
async def test_seed_admin_refuses_blank_password(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    """Referência do Railway que não resolveu chega vazia: nunca vira senha vazia do admin."""
    monkeypatch.setenv("ADMIN_EMAIL", "vazio@goodies.test")
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    called: list[str] = []

    async def fake_upsert(*_a: object) -> None:
        called.append("upsert")

    monkeypatch.setattr(seed_admin, "upsert_admin", fake_upsert)
    with pytest.raises(SystemExit) as exc:
        await seed_admin.seed_admin()
    assert exc.value.code == 1
    assert called == []
