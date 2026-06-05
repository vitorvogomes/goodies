"""Tests for portfolio targets (seeding and CRUD)."""
from __future__ import annotations

import uuid
from typing import Any

import pytest


@pytest.fixture
async def _cleanup_targets(pool: Any) -> None:
    """Clean up test users and portfolio targets after test."""
    yield
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM portfolio_targets WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'test_%_%@test.com')"
        )
        await conn.execute(
            "DELETE FROM users WHERE email LIKE 'test_%_%@test.com'"
        )


class TestSeedPortfolioTargets:
    """Test seeding and retrieving portfolio targets."""

    @pytest.mark.asyncio
    async def test_seed_targets_creates_six_categories(
        self, pool: Any, _cleanup_targets: None
    ) -> None:
        """Seed should create exactly 6 portfolio targets for a user."""
        from engines.portfolio.targets import PORTFOLIO_TARGETS, seed_targets

        email = f"test_seed_{uuid.uuid4().hex[:8]}@test.com"
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "INSERT INTO users (email, password_hash) "
                "VALUES ($1, 'test') RETURNING id",
                email,
            )

        rows_affected = await seed_targets(pool, user_id)
        assert rows_affected == 6, f"Expected 6 targets, got {rows_affected}"

        async with pool.acquire() as conn:
            targets = await conn.fetch(
                "SELECT category, target_pct FROM portfolio_targets "
                "WHERE user_id = $1 ORDER BY category",
                user_id,
            )

        assert len(targets) == 6, "Should have exactly 6 rows"
        target_dict = {t["category"]: t["target_pct"] for t in targets}

        for expected in PORTFOLIO_TARGETS:
            assert (
                expected["category"] in target_dict
            ), f"Missing category: {expected['category']}"
            assert (
                target_dict[expected["category"]]
                == expected["target_pct"]
            ), f"Target mismatch for {expected['category']}"

    @pytest.mark.asyncio
    async def test_seed_targets_idempotent(
        self, pool: Any, _cleanup_targets: None
    ) -> None:
        """Seeding twice should yield same result (idempotent upsert)."""
        from engines.portfolio.targets import seed_targets

        email = f"test_idem_{uuid.uuid4().hex[:8]}@test.com"
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "INSERT INTO users (email, password_hash) "
                "VALUES ($1, 'test') RETURNING id",
                email,
            )

        rows_1 = await seed_targets(pool, user_id)
        rows_2 = await seed_targets(pool, user_id)

        assert (
            rows_1 == 6
        ), f"First seed should affect 6 rows, got {rows_1}"
        assert (
            rows_2 == 6
        ), f"Second seed should affect 6 rows (upsert), got {rows_2}"

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM portfolio_targets WHERE user_id = $1",
                user_id,
            )

        assert count == 6, "Total rows should still be 6 after second seed"

    @pytest.mark.asyncio
    async def test_targets_sum_100_percent(
        self, pool: Any, _cleanup_targets: None
    ) -> None:
        """Portfolio targets should sum to exactly 100%."""
        from engines.portfolio.targets import seed_targets

        email = f"test_sum_{uuid.uuid4().hex[:8]}@test.com"
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "INSERT INTO users (email, password_hash) "
                "VALUES ($1, 'test') RETURNING id",
                email,
            )

        await seed_targets(pool, user_id)

        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT SUM(target_pct) FROM portfolio_targets "
                "WHERE user_id = $1",
                user_id,
            )

        assert total == 100.0, f"Targets should sum to 100%, got {total}"

    @pytest.mark.asyncio
    async def test_get_targets_returns_list(
        self, pool: Any, _cleanup_targets: None
    ) -> None:
        """get_targets should return list of target dicts."""
        from engines.portfolio.targets import get_targets, seed_targets

        email = f"test_get_{uuid.uuid4().hex[:8]}@test.com"
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "INSERT INTO users (email, password_hash) "
                "VALUES ($1, 'test') RETURNING id",
                email,
            )

        await seed_targets(pool, user_id)
        targets = await get_targets(pool, user_id)

        assert isinstance(targets, list), "get_targets should return list"
        assert len(targets) == 6, "Should have 6 targets"

        for target in targets:
            assert "category" in target, "Each target should have 'category'"
            assert "target_pct" in target, "Each target should have 'target_pct'"

    @pytest.mark.asyncio
    async def test_get_targets_empty_for_new_user(
        self, pool: Any, _cleanup_targets: None
    ) -> None:
        """get_targets for unseeded user should return empty list."""
        from engines.portfolio.targets import get_targets

        email = f"test_empty_{uuid.uuid4().hex[:8]}@test.com"
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "INSERT INTO users (email, password_hash) "
                "VALUES ($1, 'test') RETURNING id",
                email,
            )

        targets = await get_targets(pool, user_id)
        assert targets == [], "Unseeded user should have empty targets list"
