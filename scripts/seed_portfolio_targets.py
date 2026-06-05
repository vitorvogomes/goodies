#!/usr/bin/env python3
"""Seed portfolio targets for the admin user. Idempotent."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from config import settings
from db.connection import close_pool, init_pool
from engines.portfolio.targets import PORTFOLIO_TARGETS, seed_targets


async def main() -> None:
    """Seed portfolio targets for the admin user."""
    dry_run = "--dry-run" in sys.argv

    print("=" * 70)
    print("PORTFOLIO TARGETS SEEDER")
    print("=" * 70)

    try:
        await init_pool(settings.database_url)

        from db.connection import get_pool

        pool = get_pool()

        async with pool.acquire() as conn:
            admin = await conn.fetchrow(
                "SELECT id, email FROM users ORDER BY created_at LIMIT 1"
            )

        if not admin:
            print("❌ No users found in database. Please seed a user first.")
            sys.exit(1)

        user_id = admin["id"]
        print(f"✓ Admin user: {admin['email']} (id={user_id})")
        print()
        print("Targets to be seeded:")
        for target in PORTFOLIO_TARGETS:
            print(f"  • {target['category']:20s} {target['target_pct']:6.1f}%")

        print(f"\nTotal allocation: {sum(t['target_pct'] for t in PORTFOLIO_TARGETS):.1f}%")
        print()

        if dry_run:
            print("(dry-run mode — no changes made)")
        else:
            rows = await seed_targets(pool, user_id)
            print(f"✓ Seeded {rows} portfolio targets")

        print("=" * 70)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
