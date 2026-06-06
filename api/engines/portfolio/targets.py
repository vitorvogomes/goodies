"""Portfolio targets engine — allocation goals per asset category."""
from __future__ import annotations

from typing import Any

from .constants import AssetCategory

PORTFOLIO_TARGETS = [
    {"category": AssetCategory.ACOES, "target_pct": 10.0},
    {"category": AssetCategory.APOSENTADORIA, "target_pct": 12.5},
    {"category": AssetCategory.CRIPTO, "target_pct": 5.0},
    {"category": AssetCategory.ETFS, "target_pct": 12.5},
    {"category": AssetCategory.FIIS, "target_pct": 10.0},
    {"category": AssetCategory.RENDA_FIXA, "target_pct": 50.0},
]


async def seed_targets(pool: Any, user_id: str) -> int:
    """
    Seed or update portfolio targets for a user. Idempotent upsert.

    Args:
        pool: asyncpg connection pool
        user_id: UUID of the user

    Returns:
        Number of rows affected
    """
    query = """
        INSERT INTO portfolio_targets (user_id, category, target_pct)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, category)
        DO UPDATE SET target_pct = EXCLUDED.target_pct
    """

    async with pool.acquire() as conn:
        async with conn.transaction():
            count = 0
            for target in PORTFOLIO_TARGETS:
                await conn.execute(
                    query,
                    user_id,
                    target["category"],
                    target["target_pct"],
                )
                count += 1

            return count


async def get_targets(pool: Any, user_id: str) -> list[dict[str, Any]]:
    """
    Retrieve portfolio targets for a user.

    Args:
        pool: asyncpg connection pool
        user_id: UUID of the user

    Returns:
        List of dicts with 'category' and 'target_pct' keys, ordered by category
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT category, target_pct
            FROM portfolio_targets
            WHERE user_id = $1
            ORDER BY category
            """,
            user_id,
        )

    return [dict(row) for row in rows]
